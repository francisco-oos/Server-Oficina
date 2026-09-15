# Aplicar OpenAI Alpha4 Review R1

Este paquete **no es un proyecto nuevo**. Es un relevo sobre la rama de Claude:

`claude/server-oficina-review-evolution-ybrrp7`

Commit obligatorio:

`0945a438a69ce33b34d532c2b7be7157b88f943b`

## Linux

Copie `OPENAI_ALPHA4_R1.patch` a la raíz del repositorio y ejecute:

```bash
git switch claude/server-oficina-review-evolution-ybrrp7
git status
bash scripts/APLICAR_OPENAI_R1.sh
```

## Windows / PowerShell

```powershell
git switch claude/server-oficina-review-evolution-ybrrp7
git status
.\scripts\APLICAR_OPENAI_R1.ps1
```

## Gates después de aplicar

```bash
python3 scripts/syntax-check.py app tests run.py
pytest -q
node --check app/static/app.js
node --check app/static/admin-management.js
python3 scripts/check-frontend-contract.py
./VALIDAR_BACKEND.sh
./VALIDAR_FRONTEND.sh
./VALIDAR_DESPLIEGUE.sh
./VALIDAR_FRONTEND_E2E.sh
```

No desplegar en la Latitude hasta que estos gates pasen y la revisión manual de
la interfaz sea aceptada.
