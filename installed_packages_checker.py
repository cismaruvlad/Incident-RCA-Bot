from importlib.metadata import version

packages = [
    'langchain',
    'langchain-openai',
    'langchain-core',
    'fastapi',
    'openai',
    'sqlalchemy',
    'pydantic',
    'structlog',
    'httpx',
    'tenacity',
    'asyncpg',
    'alembic',
    'uvicorn',
    'pytest',
]

print('Package Versions:')
print('-' * 40)
for pkg in packages:
    try:
        v = version(pkg)
        print(f'  {pkg:30s} {v}')
    except Exception as e:
        print(f'  {pkg:30s} NOT FOUND')

print('-' * 40)
print('All checks complete!')
