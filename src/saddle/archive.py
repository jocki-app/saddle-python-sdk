"""SADDLE v1 binary archives. Values are opaque; unknown named records survive edits."""
from __future__ import annotations
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import copy
import json
import os
import struct
import tempfile

MAGIC = b'SADDLE01'
HEADER_SIZE = 144
SLOT_SIZE = 68
MAX_INDEX = 16 * 1024 * 1024
MAX_SAFE = 2**53 - 1

class SaddleError(ValueError):
    """An invalid archive, unsafe path, or conflicting operation."""

def record_name(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith('/') or '\\' in value or any(ord(c)<32 or c==':' for c in value):
        raise SaddleError('Expected a portable relative record name')
    if any(p in ('', '.', '..') or p.lower()=='.saddle' for p in value.split('/')):
        raise SaddleError('Invalid or reserved record name')
    return value

def _number(value):
    return type(value) is int and 0 <= value <= MAX_SAFE

def _loads(value):
    def invalid(value):
        raise SaddleError('Invalid JSON number: '+value)
    try:
        return json.loads(value,parse_constant=invalid)
    except (ValueError,UnicodeError) as exc:
        raise SaddleError('Invalid record index JSON') from exc

def _sync_directory(directory):
    if os.name != 'nt':
        fd=os.open(directory,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)

class Archive:
    """Durable named-record access, independent of Automerge and any application.

    Writers must hold a root lease when another application may write concurrently.
    This class serializes cooperating Python writers with an OS advisory lock.
    """
    def __init__(self,path):
        self.path=Path(path)

    @contextmanager
    def _lock(self):
        locks=Path(tempfile.gettempdir())/'saddle-python-locks'
        locks.mkdir(mode=0o700,exist_ok=True)
        name=sha256(str(self.path.absolute()).encode()).hexdigest()+'.lock'
        with (locks/name).open('a+b') as file:
            if os.name == 'nt':
                import msvcrt
                file.seek(0);file.write(b'\0');file.flush();file.seek(0)
                msvcrt.locking(file.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(file,fcntl.LOCK_EX)
            try:yield
            finally:
                if os.name == 'nt':
                    file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(file,fcntl.LOCK_UN)

    def _commit(self):
        if not self.path.exists():return None
        with self.path.open('rb') as file:
            header=file.read(HEADER_SIZE)
            if len(header)!=HEADER_SIZE or header[:8]!=MAGIC:
                raise SaddleError('Invalid SADDLE binary container')
            slots=[]
            for slot in range(2):
                raw=header[8+slot*SLOT_SIZE:8+(slot+1)*SLOT_SIZE]
                if sha256(raw[:36]).digest()!=raw[36:]:continue
                generation,offset,length,end=struct.unpack('<QQIQ',raw[:28])
                if not all(_number(n) for n in (generation,offset,length,end)) or not generation or offset<HEADER_SIZE or length>MAX_INDEX or offset+length!=end:continue
                slots.append((generation,offset,length,end,raw[28:36],slot))
            for generation,offset,length,end,digest,slot in sorted(slots,reverse=True):
                file.seek(offset);data=file.read(length)
                if len(data)!=length or sha256(data).digest()[:8]!=digest:continue
                index=_loads(data)
                if not isinstance(index,dict):raise SaddleError('Invalid SADDLE record index')
                for name,entry in index.items():
                    record_name(name)
                    if not isinstance(entry,dict) or not isinstance(entry.get('chunks'),list):raise SaddleError('Invalid record extent')
                    for chunk in entry['chunks']:
                        if not isinstance(chunk,dict) or not all(_number(chunk.get(k)) for k in ('offset','length')) or chunk['offset']<HEADER_SIZE or chunk['offset']+chunk['length']>offset or not isinstance(chunk.get('hash'),str) or len(chunk['hash'])!=64 or any(c not in '0123456789abcdef' for c in chunk['hash']):raise SaddleError('Invalid record extent')
                    if 'numChanges' in entry and not _number(entry['numChanges']):raise SaddleError('Invalid document change count')
                    if 'heads' in entry and (not isinstance(entry['heads'],list) or any(not isinstance(v,str) for v in entry['heads'])):raise SaddleError('Invalid document heads')
                return dict(generation=generation,end=end,index=index,slot=slot)
        raise SaddleError('SADDLE container has no intact commit')

    def inspect(self):
        commit=self._commit()
        return copy.deepcopy(commit or dict(generation=0,end=HEADER_SIZE,index={},slot=None))

    def names(self):return list(self.inspect()['index'])

    def read(self,name):
        record_name(name)
        entry=self.inspect()['index'].get(name)
        if entry is None:return None
        output=bytearray()
        with self.path.open('rb') as file:
            for chunk in entry['chunks']:
                file.seek(chunk['offset']);data=file.read(chunk['length'])
                if len(data)!=chunk['length'] or sha256(data).hexdigest()!=chunk['hash']:raise SaddleError('Damaged SADDLE record: '+name)
                output.extend(data)
        return bytes(output)

    def verify(self):
        for name in self.names():self.read(name)
        return self.inspect()

    def get_json(self,name):
        value=self.read(name)
        return _loads(value) if value is not None else None

    def set_json(self,name,value):
        self.write(name,(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode())

    @staticmethod
    def _slot(generation,offset,length,end,index):
        prefix=struct.pack('<QQIQ',generation,offset,length,end)+sha256(index).digest()[:8]
        return prefix+sha256(prefix).digest()

    def _replace(self,index,payloads,generation):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='.'+self.path.name+'-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w+b') as file:
                file.write(MAGIC+b'\0'*(HEADER_SIZE-8))
                cursor=HEADER_SIZE;fresh={}
                for name,entry in index.items():
                    start=cursor;digest=sha256()
                    data=payloads.get(name)
                    if data is not None:
                        file.write(data);digest.update(data);cursor+=len(data)
                    else:
                        with self.path.open('rb') as source:
                            for chunk in entry['chunks']:
                                source.seek(chunk['offset']);remaining=chunk['length'];checksum=sha256()
                                while remaining:
                                    block=source.read(min(remaining,1024*1024))
                                    if not block:raise SaddleError('Truncated SADDLE record')
                                    checksum.update(block);digest.update(block);file.write(block)
                                    remaining-=len(block);cursor+=len(block)
                                if checksum.hexdigest()!=chunk['hash']:raise SaddleError('Damaged SADDLE record during compaction')
                    fresh[name]={**{k:copy.deepcopy(v) for k,v in entry.items() if k!='chunks'},'chunks':[dict(offset=start,length=cursor-start,hash=digest.hexdigest())]}
                encoded=json.dumps(fresh,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
                if len(encoded)>MAX_INDEX:raise SaddleError('SADDLE record index is too large')
                file.write(encoded);file.flush();os.fsync(file.fileno())
                file.seek(8);file.write(self._slot(generation,cursor,len(encoded),cursor+len(encoded),encoded));file.flush();os.fsync(file.fileno())
            os.replace(temp,self.path);_sync_directory(self.path.parent)
        finally:
            if os.path.exists(temp):os.unlink(temp)

    def write(self,name,data,*,append=False,heads=None,num_changes=None):
        record_name(name)
        if not isinstance(data,bytes):raise TypeError('Record payload must be bytes')
        if heads is not None and (not isinstance(heads,list) or any(not isinstance(h,str) for h in heads)):raise SaddleError('Invalid document heads')
        if num_changes is not None and not _number(num_changes):raise SaddleError('Invalid document change count')
        with self._lock():
            old=self._commit();index=copy.deepcopy(old['index']) if old else {};offset=old['end'] if old else HEADER_SIZE
            prior=index.get(name,{})
            if append and not data and prior.get('heads')==heads and prior.get('numChanges')==num_changes:return
            entry={'chunks':(prior.get('chunks',[]) if append else [])+[dict(offset=offset,length=len(data),hash=sha256(data).hexdigest())]}
            if heads is not None:entry['heads']=heads
            if num_changes is not None:entry['numChanges']=num_changes
            index[name]=entry
            # Epoch replacement discards the old archive bytes rather than only hiding them.
            live=sum(chunk['length'] for entry in index.values() for chunk in entry['chunks'])
            if old and (name.endswith('.automerge') and not append or offset>8*1024*1024 and live<offset/2):
                values={name:data}
                self._replace(index,values,old['generation']+1);return
            encoded=json.dumps(index,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            if len(encoded)>MAX_INDEX:raise SaddleError('SADDLE record index is too large')
            at=offset+len(data);end=at+len(encoded)
            if old:
                with self.path.open('r+b') as file:
                    file.seek(offset);file.write(data);file.write(encoded);file.flush();os.fsync(file.fileno())
                    file.seek(8+(1-old['slot'])*SLOT_SIZE);file.write(self._slot(old['generation']+1,at,len(encoded),end,encoded));file.flush();os.fsync(file.fileno())
            else:self._replace(index,{name:data},1)

    def remove(self,name):
        record_name(name)
        with self._lock():
            old=self._commit()
            if not old or name not in old['index']:return
            index={k:v for k,v in old['index'].items() if k!=name}
            self._replace(index,{},old['generation']+1)

    def compact(self):
        with self._lock():
            old=self._commit()
            if old:self._replace(old['index'],{},old['generation']+1)
