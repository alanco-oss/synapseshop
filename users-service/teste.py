

from database import SessionLocal
from repository.token_repository import TokenRepository
from repository.user_repository import UserRepository
from services.auth_service import AuthService, CredenciaisInvalidasError

db = SessionLocal()
user_repo = UserRepository(db)
token_repo = TokenRepository(db)
auth_service = AuthService(user_repo, token_repo)

# Login válido (usando o usuário de teste que já existe)
token = auth_service.login(email="teste@synapseshop.com", senha="senha123")
print(f"Token gerado: {token[:50]}...")

# Validar o token
payload = auth_service.validar_token(token)
print(f"Payload: {payload}")

# Login inválido (senha errada)
try:
    auth_service.login(email="teste@synapseshop.com", senha="senha-errada")
except CredenciaisInvalidasError as e:
    print(f"Bloqueado corretamente: {e}")

db.close()
