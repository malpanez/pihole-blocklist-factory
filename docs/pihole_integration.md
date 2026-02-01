# Integración con Pi-hole v6

## Opción A: file:// (misma máquina)
1) Clona el repo en el host donde corre Pi-hole.
2) Ejecuta el build (o descarga artifacts).
3) Añade en Pi-hole la URL:
   - file:///path/al/repo/dist/profiles/base.txt

## Opción B: servidor local (recomendado)
Sirve `dist/` con nginx/caddy y añade la URL HTTP interna en Pi-hole.

## Asignación por grupos
Pi-hole permite asignar adlists a grupos y clientes a grupos.
Esto encaja con `dist/profiles/*.txt`.
