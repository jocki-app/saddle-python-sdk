"""JSON metadata and scope policies shared by all SADDLE implementations."""
from __future__ import annotations
from copy import deepcopy
from pathlib import PurePosixPath
from urllib.parse import urlparse
import json
import re
from .archive import SaddleError, record_name

RESOURCE_PROFILE='https://datapackage.org/profiles/2.0/dataresource.json'
def companion_path(path):
    path=PurePosixPath(record_name(path))
    return str(path.parent/('.'+path.name+'.saddle'))

def _json(value):
    if value is None or type(value) in (str,bool,int):return
    if type(value) is float:
        import math
        if math.isfinite(value):return
    elif isinstance(value,list):
        for item in value:_json(item)
        return
    elif isinstance(value,dict):
        for key,item in value.items():
            if not isinstance(key,str) or key=='__proto__':raise SaddleError('Invalid metadata property')
            _json(item)
        return
    raise SaddleError('Metadata must contain finite JSON values')

def resource_path(value):
    if not isinstance(value,str) or not value:raise SaddleError('Resource path must be nonempty text')
    parsed=urlparse(value)
    if parsed.scheme in ('http','https') and parsed.netloc:return value
    if parsed.scheme or value.startswith('//'):raise SaddleError('Resource paths must be relative or HTTP(S) URLs')
    record_name(value[2:] if value.startswith('./') else value)
    return value

def resource(value):
    if isinstance(value,(str,bytes)):value=json.loads(value)
    _json(value)
    if not isinstance(value,dict) or not isinstance(value.get('name'),str) or not value['name'].strip():raise SaddleError('A Data Resource requires a name')
    if ('path' in value)==('data' in value):raise SaddleError('A Data Resource requires exactly one of path or data')
    if 'path' in value:
        paths=value['path'] if isinstance(value['path'],list) else [value['path']]
        if not paths:raise SaddleError('Resource path must not be empty')
        for path in paths:resource_path(path)
        if len({urlparse(path).scheme in ('http','https') for path in paths})>1:raise SaddleError('Resource paths cannot mix local paths and URLs')
    if 'data' in value:
        if not isinstance(value['data'],(str,dict,list)):raise SaddleError('Invalid inline resource data')
        if isinstance(value['data'],str) and not value.get('format') and not value.get('mediatype'):raise SaddleError('Inline text requires format or mediatype')
    for key in ('metadata','saddle'):
        if key in value and not isinstance(value[key],dict):raise SaddleError(key+' must be an object')
    if 'contentType' in value.get('saddle',{}) and (not isinstance(value['saddle']['contentType'],str) or not value['saddle']['contentType'].strip()):raise SaddleError('saddle.contentType must be nonempty text')
    return deepcopy(value)

def new_resource(path):
    name=PurePosixPath(path).name
    stem=name.rsplit('.',1)[0] if '.' in name else name
    return {'$schema':RESOURCE_PROFILE,'name':re.sub('[^a-z0-9._-]','-',stem.lower()) or 'file','path':name}

def import_metadata(path,source='',descriptor=None):
    inline={}
    if str(path).lower().endswith('.md'):
        match=re.match(r'^---\s*\n([\s\S]*?)\n---(?:\n|$)',source)
        if match:
            import yaml
            inline=yaml.safe_load(match[1])
            if not isinstance(inline,dict):raise SaddleError('Markdown properties must be a YAML map')
    _json(inline)
    properties={};links=[]
    def add(values):
        for key,value in values.items():
            if key in properties:raise SaddleError('Metadata conflict: '+key+' is defined more than once')
            properties[key]=value
    if descriptor:
        descriptor=resource(descriptor)
        add({k:v for k,v in descriptor.items() if k not in ('path','data','metadata')})
        add(descriptor.get('metadata',{}))
        if 'path' in descriptor:
            links=descriptor['path'] if isinstance(descriptor['path'],list) else [descriptor['path']]
            if 'path' in inline:raise SaddleError('Metadata conflict: path is defined more than once')
    add({k:v for k,v in inline.items() if k not in ('path','metadata')})
    if 'metadata' in inline:
        if not isinstance(inline['metadata'],dict):raise SaddleError('Inline metadata must be an object')
        add(inline['metadata'])
    if 'path' in inline:
        values=inline['path'] if isinstance(inline['path'],list) else [inline['path']]
        links += [resource_path(v) for v in values]
    return dict(resource=descriptor,properties=properties,links=links,contentType=(descriptor or {}).get('saddle',{}).get('contentType'))

def effective_features(policies,workspace,path,identity=None):
    result={'history':False,'sync':False,**workspace,**policies.get('vault',{})}
    parts=path.split('/')
    for length in range(1,len(parts)):
        result.update(policies.get('folders',{}).get('/'.join(parts[:length]),{}))
    if identity:result.update(policies.get('files',{}).get(identity,{}))
    return result
