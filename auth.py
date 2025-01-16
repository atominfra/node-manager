import base64
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from fastapi import Request, HTTPException
import json
    
class AuthGuard:
    def __init__(self, public_key: str, passphrase: str):
        self.public_key = public_key
        self.passphrase = passphrase
        
    def verify_signature(self, data, signature):
        
        try:
            signature_bytes = base64.b64decode(signature)
                        
            data_hash = SHA256.new(data.encode("utf-8"))
                        
            rsa_key = RSA.import_key(self.public_key, self.passphrase)
            
            pkcs1_15.new(rsa_key=rsa_key).verify(data_hash, signature_bytes)
            
            return True
        except Exception as e:
            print(e)
            return False
        
    async def authenticate(self, request: Request):
        signature = (request.headers.get("X-API-Signature"))
        
        if not signature:
            return HTTPException(401)
        
        data = None
        
        if request.method == "POST" or request.method == "PATCH":
            data = await request.json()
        else:
            path = request.url.path.lstrip("/")
            query_params = dict(request.query_params)
            
            data = {
                "path": path,
                "query_params": query_params
            }
            
        data = json.dumps(data)
            
        valid = self.verify_signature(data, signature)
        
        if not valid:
            raise HTTPException(401)