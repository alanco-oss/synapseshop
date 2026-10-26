
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nome: str
    role: str

class UserPaginados(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    page: int
    size: int
    usuarios: list[UserResponse]
