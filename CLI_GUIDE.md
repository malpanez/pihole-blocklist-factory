# CLI Simplificada con Click

## 🎉 Cambio Major: De `python3 -c` a Comandos Simples

**Antes** (tedioso):
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build']))"
```

**Después** (mucho mejor):
```bash
uv run blocklist-factory build
```

---

## 📖 Referencia Rápida de Comandos

### Setup (una sola vez)
```bash
# Instalar click y la herramienta
uv pip install click
uv pip install -e .
```

### Comandos Disponibles

#### 1. **Validate** - Validar configuración
```bash
uv run blocklist-factory validate
```
- Verifica que la configuración sea válida
- Muestra cantidad de fuentes, perfiles y precedencia
- **Útil**: Antes de hacer build

#### 2. **Sync Firebog** - Descarga catálogo público
```bash
uv run blocklist-factory sync-firebog
```
- Descarga las 150+ listas públicas de Firebog
- Crea `config/sources.firebog.yml`
- **Opcional**: `--dry-run` para ver sin escribir

#### 3. **Build** - Construir blocklists
```bash
# Normal (con descarga de red, paralelizado)
uv run blocklist-factory build

# Offline (usa caché)
uv run blocklist-factory build --no-fetch

# Salida JSON
uv run blocklist-factory build --json
```
- **Tiempo**: 10-15 min (primer run), 4-7 min (caché)
- Genera: `dist/all.txt`, categorías, perfiles, reportes

#### 4. **Analyze** - Análisis de calidad
```bash
uv run blocklist-factory analyze
```
- Detecta problemas de calidad
- Calcula overlap entre fuentes
- Genera `dist/reports/quality.md`

#### 5. **Recommend** - Recomendaciones de carga
```bash
uv run blocklist-factory recommend
```
- Ranking de fuentes por valor
- Calcula contribución única
- Genera `dist/reports/recommend.md`

#### 6. **Report** - Ver estadísticas últimas
```bash
uv run blocklist-factory report
```
- Muestra stats en JSON
- Úsalo para revisar números

---

## 🚀 Flujo Típico (Completo)

```bash
# 1. Validar config
uv run blocklist-factory validate

# 2. Sincronizar Firebog (opcional si es primera vez)
uv run blocklist-factory sync-firebog

# 3. Build (toma 10-15 min)
uv run blocklist-factory build

# 4. Analizar calidad
uv run blocklist-factory analyze

# 5. Generar recomendaciones
uv run blocklist-factory recommend

# 6. Ver resultados
cat dist/reports/recommend.md
cat dist/reports/quality.md
```

---

## 💡 Ejemplos Prácticos

### Desarrollo rápido (con test data)
```bash
export BLOCKLIST_SOURCES=test
uv run blocklist-factory build        # <1 segundo
uv run blocklist-factory analyze      # instantáneo
uv run blocklist-factory recommend    # instantáneo
```

### Producción (con Firebog)
```bash
# Primera vez
uv run blocklist-factory sync-firebog   # 1 min
uv run blocklist-factory build          # 10-15 min

# Runs posteriores (caché activo)
uv run blocklist-factory build          # 4-7 min
```

### Customizar workers (servidor potente)
```bash
export BLOCKLIST_WORKERS=12
uv run blocklist-factory build

# Resultado: ~8-12 min en lugar de 10-15 min
```

### Raspberry Pi (recursos limitados)
```bash
export BLOCKLIST_WORKERS=2
uv run blocklist-factory build --no-fetch

# Resultado: ~10 min, uso mínimo de RAM
```

---

## 🛠️ Opciones Avanzadas

### Build con flag --json
```bash
uv run blocklist-factory build --json > stats.json
```
- Salida en formato JSON para scripts
- Útil para CI/CD

### Sync Firebog con --dry-run
```bash
uv run blocklist-factory sync-firebog --dry-run
```
- Ver qué se generaría sin escribir archivos
- Útil para testing

---

## 📊 Ventajas de la Nueva CLI

| Aspecto | Antes | Ahora |
|--------|-------|-------|
| Comando | `python3 -c "..."` (100+ chars) | `blocklist-factory build` (20 chars) |
| Legibilidad | ❌ Ilegible | ✅ Clara |
| Autocompletado | ❌ No | ✅ Sí (con zsh/bash) |
| Help | ❌ Confuso | ✅ Claro |
| Opciones | ❌ Ocultas en código | ✅ Documentadas |
| Error handling | ❌ Stack trace largo | ✅ Mensajes claros |
| Colores | ❌ No | ✅ Sí (rojo/verde) |

---

## 🔧 Instalación para Desarrollo

Si quieres editar código y que se refleje inmediatamente:

```bash
# Instalar en modo editable
uv pip install -e .

# Los comandos se actualizarán automáticamente
```

---

## 🎯 Comparativa: Antes vs Después

### Antes (argparse manual):
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build', '--no-fetch']))"
```

### Ahora (Click):
```bash
uv run blocklist-factory build --no-fetch
```

**Factor de mejora**: ~5x más simple y legible

---

## ✨ Tecnología: Click

- **Click**: Framework Python para CLI elegantes
- **Decorators**: `@click.command()`, `@click.option()`
- **Auto-help**: Generado automáticamente de docstrings
- **Type hints**: Integración con Python 3.11+
- **Colores**: Support integrado para terminal

**Dependencia agregada**: `click>=8.1.0` (ligero, 10 KB)

---

## 📝 Resumen

**La CLI ahora es usable y profesional**:
- ✅ Comandos simples y memorables
- ✅ Help integrado (`blocklist-factory --help`)
- ✅ Opciones documentadas
- ✅ Colores en salida
- ✅ Error messages claros
- ✅ Listo para CI/CD

**Próximo paso**: Ejecuta `uv run blocklist-factory validate` para confirmar que todo funciona.

---

**Última actualización**: 2026-01-31
**Versión**: 1.0.2 (CLI Upgrade)
