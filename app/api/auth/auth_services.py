from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.userModel import User, Role
from app.schemas.userSchema import UserCreate


class UserService:

    @staticmethod
    def register_user(db: Session, user_create: UserCreate) -> User:
        """
        Registra un nuevo usuario en la base de datos.
        Args:
            db (Session): Sesión de la base de datos.
            user_create (UserCreate): Datos del usuario a registrar.
        Returns:
            User: Usuario registrado.
        Raises:
            HTTPException: Si el correo electrónico ya está registrado o si el rol no existe.
        """
        # Verificar si el correo electrónico ya está registrado
        existing_user = db.query(User).filter(User.email == user_create.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya está registrado."
            )

        # Verificar si el rol existe
        role = db.query(Role).filter(Role.id == user_create.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El rol especificado no existe."
            )

        # comparar contraseña y confirmación de contraseña
        if user_create.password != user_create.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña y la confirmación de contraseña no coinciden."
            )

        if not user_create.terms_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes aceptar los términos y condiciones para registrarte.",
            )
        
        # Crear el nuevo usuario
        new_user = User(
            full_name=user_create.full_name,
            email=user_create.email,
            hashed_password=get_password_hash(user_create.password),
            terms_accepted=user_create.terms_accepted,
            role_id=user_create.role_id
        )
        db.add(new_user) # Agregar el nuevo usuario a la sesión
        db.commit() # Guardar los cambios en la base de datos
        db.refresh(new_user) # Actualizar el objeto new_user con los datos de la base de datos (por ejemplo, el ID generado automáticamente)
        return new_user

    @staticmethod
    def login_user(db: Session, email: str, password: str) -> dict:
        """
        Autentica a un usuario.
        Args:
            db (Session): Sesión de la base de datos.
            email (str): Correo electrónico del usuario.
            password (str): Contraseña del usuario.
        Returns:
            User: Usuario autenticado.
        Raises:
            HTTPException: Si el correo electrónico no está registrado o si la contraseña es incorrecta.
        """
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo electrónico o contraseña incorrectos.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="contraseña incorrecta o usuario inactivo.",
            )

        
        return {
            "user": user,
            "access_token": create_access_token(data={
                "sub": str(user.id),
                "email": user.email,
            }),
            "token_type": "bearer",
        }