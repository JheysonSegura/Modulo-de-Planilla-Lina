"""Otorga (o revoca) la bandera global usuarios.es_superadmin.

Es el ÚNICO mecanismo para dar de alta un superadmin -- deliberadamente
no existe ningún endpoint ni pantalla para esto (ver CLAUDE.md sección
de superadmin): requiere acceso directo a la infraestructura, igual
que seed_dev.py con el primer usuario/empresa.

Uso (dentro del contenedor backend, o localmente con DATABASE_URL
apuntando a la BD correspondiente):

    python -m scripts.otorgar_superadmin correo@empresa.com
    python -m scripts.otorgar_superadmin correo@empresa.com --revocar
"""
import argparse
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Usuario


def run(email: str, otorgar: bool) -> None:
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        usuario = session.scalar(select(Usuario).where(Usuario.email == email))
        if usuario is None:
            print(f"No existe ningún usuario con el email '{email}'.")
            sys.exit(1)

        usuario.es_superadmin = otorgar
        session.commit()
        verbo = "otorgada a" if otorgar else "revocada de"
        print(f"Bandera de superadmin {verbo} {email} (id: {usuario.id}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument(
        "--revocar", action="store_true", help="Quita la bandera en vez de otorgarla"
    )
    args = parser.parse_args()
    run(args.email, otorgar=not args.revocar)
