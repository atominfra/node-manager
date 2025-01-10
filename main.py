
from typing import Dict
import docker
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


client = docker.from_env() 

class RegistryCredentials(BaseModel):
    username: str
    password: str
    
class CreateServiceRequest(BaseModel):
    name: str
    image_url: str
    registry_credentials: RegistryCredentials = None    
    memory_limit: str = None
    cpu_limit: str = None
    environment_variables: Dict[str, str] = None

# write a function that takes image url, registry credentials (use them to pull private image), container name, memory limit, cpu limit, environment variables and starts a container and returns the container id
@app.post("/")
def start_container(request: CreateServiceRequest):
    if request.registry_credentials:
        client.login(username=request.registry_credentials.username, password=request.registry_credentials.password)
    
    container = client.containers.run(
        image=request.image_url,
        name=request.name,
        detach=True,
        mem_limit=request.memory_limit,
        environment=request.environment_variables,
        cpu_count=request.cpu_limit
    )
    return {"container_id": container.id}