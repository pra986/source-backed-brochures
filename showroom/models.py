from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Fuel = Literal['petrol','diesel','electric','hybrid']
Transmission = Literal['manual','automatic']
Body = Literal['hatchback','sedan','suv']
class Search(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_price: int | None = Field(default=None, ge=0, le=100_000_000)
    min_price: int | None = Field(default=None, ge=0, le=100_000_000)
    brand: str | None = Field(default=None, max_length=60)
    fuel: Fuel | None = None
    transmission: Transmission | None = None
    body_type: Body | None = None
    available_only: bool = True
    @model_validator(mode='after')
    def price_order(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError('Minimum price must not exceed maximum price.')
        return self
class Compare(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=3)
    @field_validator('ids')
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value): raise ValueError('Choose distinct cars.')
        return value
class Register(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: SecretStr = Field(min_length=10, max_length=128)
    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('Name cannot be blank.')
        return value.strip()
class Login(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)
class Preview(BaseModel):
    car_id: str = Field(min_length=1, max_length=30)
class Confirm(BaseModel):
    preview_id: str = Field(min_length=1, max_length=64)
    confirmed: Literal[True]
class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    mode: Literal['offline','ai'] = 'offline'
class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['search','compare','details','help']
    filters: Search = Field(default_factory=Search)
    ids: list[str] = Field(default_factory=list, max_length=3)
