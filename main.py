
from typing import Dict
import docker
from fastapi import FastAPI
from pydantic import BaseModel
from docker.errors import APIError
import requests
from .config import config
from .auth import AuthGuard
from fastapi import Request, HTTPException, Depends

app = FastAPI()

CADDY_ADMIN_URL = config.get("CADDY_ADMIN_URL")
DOCKER_NETWORK =  "atominfra"

PUBLIC_KEY = config.get("PUBLIC_KEY")

auth_guard = AuthGuard(PUBLIC_KEY)

async def secure(request: Request):
    if not (request.headers.get("X-API-Signature")):
        raise HTTPException(401)  
    
    return await auth_guard.authenticate(request=request)


client = docker.from_env() 

class RegistryCredentials(BaseModel):
    username: str
    password: str
    
class CreateServiceRequest(BaseModel):
    name: str
    image_url: str
    registry_credentials: RegistryCredentials = None    
    memory_limit: str = None
    cpu_limit: float = None
    environment_variables: Dict[str, str] = None
    
class MapDomainRequest(BaseModel):
    id: str
    domain: str
    container_id: str
    container_port: int

# write a function that takes image url, registry credentials (use them to pull private image), container name, memory limit, cpu limit, environment variables and starts a container and returns the container id
@app.post("/")
def create_container(request: CreateServiceRequest, x=Depends(secure)):
    try:
        if request.registry_credentials:
            client.login(username=request.registry_credentials.username, password=request.registry_credentials.password, registry=request.registry_credentials.registry_url)
        
        container = client.containers.run(
            image=request.image_url,
            name=request.name,
            detach=True,
            mem_limit=request.memory_limit,
            environment=request.environment_variables,
            cpu_period=100000,
            cpu_quota=int(request.cpu_limit * 100000),
            network=DOCKER_NETWORK
        )
        # all the details, also send mem_limit, cpu_limit and environment variables
        return {
            "id": container.id,
            "name": container.name,
            "image": container.attrs["Config"]["Image"],
            "memory_limit": container.attrs["HostConfig"]["Memory"],
            "cpu_limit": container.attrs["HostConfig"]["CpuQuota"] / container.attrs["HostConfig"]["CpuPeriod"] if container.attrs["HostConfig"]["CpuPeriod"] else 0,
            "environment_variables": container.attrs["Config"]["Env"],
        }
    except APIError as e:
        if e.response.status_code == 409:  # Conflict error
            error_message = e.explanation.decode() if isinstance(e.explanation, bytes) else e.explanation
            if "Conflict. The container name" in error_message:
                return {"error": True, "message": "Container name conflict detected."}
            elif "Conflict. The port" in error_message:
                return {"error": True, "message": "Port conflict detected."}
            else:
                return {"error": True, "message": error_message}
        else:
            # Handle other API errors
            return {"error": True, "message": e.explanation}
    except Exception as e:
        return {"error": True, "message": str(e)}
    
# write a function to stop a container by container id
@app.get("/{container_id}/stop")
def stop_container(container_id: str, x=Depends(secure)):
    try:
        container = client.containers.get(container_id)
        container.stop()
        return {"message": "Container stopped successfully."}
    except APIError as e:
        if e.response.status_code == 404:
            return {"error": True, "message": "Container not found."}
        else:
            return {"error": True, "message": e.explanation}
    except Exception as e:
        return {"error": True, "message": str(e)}
    
# write a function to start a container by container id
@app.get("/{container_id}/start")
def start_container(container_id: str, x=Depends(secure)):
    try:
        container = client.containers.get(container_id)
        container.start()
        return {"message": "Container started successfully."}
    except APIError as e:
        if e.response.status_code == 404:
            return {"error": True, "message": "Container not found."}
        else:
            return {"error": True, "message": e.explanation}
    except Exception as e:
        return {"error": True, "message": str(e)}
    
# write a function to delete a container by container id
# take a force as query parameter, if force is true, stop the container if it is running and then delete it
@app.delete("/{container_id}")
def delete_container(container_id: str, force: bool = False, x=Depends(secure)):
    try:
        container = client.containers.get(container_id)
        if container.status == "running":
            if force:
                container.stop()
            else:
                return {"error": True, "message": "Container is running. Stop the container before deleting it."}
        container.remove()
        return {"message": "Container deleted successfully."}
    except APIError as e:
        if e.response.status_code == 404:
            return {"error": True, "message": "Container not found."}
        else:
            return {"error": True, "message": e.explanation}
    except Exception as e:
        return {"error": True, "message": str(e)}

# write a function to get a container by container id
@app.get("/{container_id}")
def get_container(container_id: str, x=Depends(secure)):
    try:
        container = client.containers.get(container_id)
        return {
            "id": container.id,
            "name": container.name,
            "image": container.attrs["Config"]["Image"],
            "memory_limit": container.attrs["HostConfig"]["Memory"],
            "cpu_limit": container.attrs["HostConfig"]["CpuQuota"] / container.attrs["HostConfig"]["CpuPeriod"] if container.attrs["HostConfig"]["CpuPeriod"] else 0,
            "environment_variables": container.attrs["Config"]["Env"]
        }
    except APIError as e:
        if e.response.status_code == 404:
            return {"error": True, "message": "Container not found."}
        else:
            return {"error": True, "message": e.explanation}
    except Exception as e:
        return {"error": True, "message": str(e)}

# write a function to get all the running containers with all the details, also send mem_limit (in mbs), cpu_limit and environment variables
@app.get("/")
def get_containers(x=Depends(secure)):   
    containers = client.containers.list()
    
    return [
        {
            "id": container.id,
            "name": container.name,
            "image": container.attrs["Config"]["Image"],
            "memory_limit": container.attrs["HostConfig"]["Memory"],
            "cpu_limit": container.attrs["HostConfig"]["CpuQuota"] / container.attrs["HostConfig"]["CpuPeriod"] if container.attrs["HostConfig"]["CpuPeriod"] else 0,
            "environment_variables": container.attrs["Config"]["Env"]
        }
        for container in containers
    ]
    
@app.post("/domain")
def map_domain(request: MapDomainRequest, x=Depends(secure)):
    try:
        route = {
            "@id": request.id,
            "handle": [
                {
                    "handler": "reverse_proxy",
                    "upstreams": [
                        {
                            "dial": f"{request.container_id[:12]}:{request.container_port}"
                        }
                    ]
                }
            ],
            "match": [
                {
                    "host": [
                        f"{request.domain}"
                    ]
                }
            ]
        }
        
        response = requests.put(f"{CADDY_ADMIN_URL}/config/apps/http/servers/srv0/routes/0", json=route)
        
        if response.status_code != 200:
            return {"error": True, "message": response.text}
        
        return {"message": "Domain Mapped Successfully"}
    except Exception as e:
        print(e)
        
        return {"error": True, "message": str(e)}
    
@app.delete("/domain/{id}")
def unmap_domain(id: str, x=Depends(secure)):
    try:
        response = requests.delete(f"{CADDY_ADMIN_URL}/id/{id}")
        
        if response.status_code != 200:
            return {"error": True, "message": response.text}
        
        return {"message": "Domain Unmapped Successfully"}
    except Exception as e:
        print(e)
        
        return {"error": True, "message": str(e)}
    
@app.post("/redeploy/{container_id}/{tag}")
def redeploy_container(container_id: str, tag: str,x=Depends(secure)):
    try:
        container = client.containers.get(container_id)
        image_url = container.attrs["Config"]["Image"]
        environment_variables = container.attrs["Config"]["Env"]
        memory_limit = container.attrs["HostConfig"]["Memory"]
        cpu_limit = container.attrs["HostConfig"]["CpuQuota"] / container.attrs["HostConfig"]["CpuPeriod"] if container.attrs["HostConfig"]["CpuPeriod"] else 0
        container_name = container.name

        if ":" in image_url:
            image_base = image_url.split(":")[0]  
        else:
            image_base = image_url 

        new_image_url = f"{image_base}:{tag}"  

        try:
            client.images.pull(new_image_url)
        except Exception as e:
            return {"error": True, "message": f"Failed to pull image {new_image_url}: {str(e)}"}

        if container.status == "running":
                container.stop()
        
        container.remove()

        new_container = client.containers.run(
            image=new_image_url,
            name=container_name,
            detach=True,
            mem_limit=memory_limit,
            environment=environment_variables,
            cpu_period=100000,
            cpu_quota=int(cpu_limit * 100000) if cpu_limit else None,
            network=DOCKER_NETWORK
        )

        return {
            "message": "Container redeployed successfully.",
            "id": new_container.id,
            "name": new_container.name,
            "image": new_container.attrs["Config"]["Image"],
            "memory_limit": new_container.attrs["HostConfig"]["Memory"],
            "cpu_limit": new_container.attrs["HostConfig"]["CpuQuota"] / new_container.attrs["HostConfig"]["CpuPeriod"] if new_container.attrs["HostConfig"]["CpuPeriod"] else 0,
            "environment_variables": new_container.attrs["Config"]["Env"]
        }
    except APIError as e:
        return {"error": True, "message": e.explanation}
    except Exception as e:
        return {"error": True, "message": str(e)}
