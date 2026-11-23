"""Language binding for the canonical Automerge and Keyhive runtime.

Container and metadata parsing are native Python. Distributed history and sharing
use the same TypeScript implementation as every other SADDLE client, through an
explicit executable capability. Data received from peers never becomes a command.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
from .archive import SaddleError
class Runtime:
    def __init__(self,command=None,*,profile=None,timeout=60):
        self.command=list(command) if command is not None else [shutil.which('saddle') or 'saddle']
        self.profile=profile;self.timeout=timeout
    def request(self,method,target,**options):
        request=dict(method=method,target=os.fspath(target),**options)
        if self.profile is not None:request['profile']=os.fspath(self.profile)
        process=subprocess.run(self.command+['rpc'],input=json.dumps(request),text=True,capture_output=True,timeout=self.timeout,check=False)
        try:value=json.loads(process.stdout)
        except ValueError as exc:raise SaddleError(process.stderr.strip() or 'SADDLE runtime returned invalid JSON') from exc
        if not value.get('ok'):raise SaddleError(value.get('error','SADDLE operation failed'))
        if process.returncode:raise SaddleError(process.stderr.strip() or 'SADDLE runtime failed')
        return value.get('result')
    def inspect(self,target):return self.request('unit.inspect',target)
    def history(self,target):return self.request('history.list',target)
    def configure(self,target,feature,state):
        if feature not in ('history','sharing') or state not in ('unset','disabled','enabled'):raise SaddleError('Invalid feature or state')
        return self.request(feature+'.configure',target,state=state)
    def reset_history(self,target):return self.request('history.reset',target)
    def delete_version(self,target,version):return self.request('history.delete',target,hash=version)
    def metadata(self,target):return self.request('metadata.get',target)
    def set_metadata(self,target,value):return self.request('metadata.set',target,value=value)
    def contact(self,target):return self.request('sharing.contact',target)['contact']
    def shares(self,target):return self.request('sharing.list',target)
    def invite(self,target):return self.request('sharing.invite',target)
    def join(self,target,invitation):return self.request('sharing.join',target,invitation=invitation)
    def grant(self,target,invitation,contact,role='read'):return self.request('sharing.grant',target,invitation=invitation,contact=contact,role=role)
    def broadcast(self,target,invitation,enabled):
        if type(enabled) is not bool:raise SaddleError('Broadcast must be a boolean')
        return self.request('sharing.broadcast',target,invitation=invitation,broadcast=enabled)
