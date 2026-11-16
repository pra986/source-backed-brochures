from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind=Literal['summary','decision','action']
class Analyze(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    transcript:str=Field(min_length=1,max_length=120000)
    mode:Literal['offline','ai']='offline'
    @field_validator('title','transcript')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Cannot be blank.')
        return value.strip()
class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    summary:list[str]=Field(default_factory=list,max_length=6)
    decision:list[str]=Field(default_factory=list,max_length=20)
    action:list[str]=Field(default_factory=list,max_length=40)
class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=64)
    text:str=Field(min_length=1,max_length=2000)
    owner:str|None=Field(default=None,max_length=100)
    due_text:str|None=Field(default=None,max_length=120)
    included:bool=True
    @field_validator('text')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Item text cannot be blank.')
        return value.strip()
class Review(BaseModel):
    revision:int=Field(ge=1)
    edits:list[Edit]=Field(max_length=100)
    reviewed:bool=False
class AddItem(BaseModel):
    revision:int=Field(ge=1)
    kind:Kind
    text:str=Field(min_length=1,max_length=2000)
    source_id:str=Field(min_length=1,max_length=20)
    owner:str|None=Field(default=None,max_length=100)
    due_text:str|None=Field(default=None,max_length=120)
    @field_validator('text')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Item text cannot be blank.')
        return value.strip()
class Delete(BaseModel):
    revision:int=Field(ge=1)
