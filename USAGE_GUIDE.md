# Guía de Uso: Blocklist Factory para Pi-hole

## Descripción General

El **Blocklist Factory** es un pipeline automatizado que:
1. Descarga catálogos de listas públicas (ej. Firebog)
2. Parsea múltiples formatos (hosts, domain-only, ABP simple)
3. Sanitiza y normaliza dominios (IDNA, validación FQDN)
4. Deduplica automáticamente
5. Analiza calidad y detecta errores
6. Genera recomendaciones de qué listas cargar en Pi-hole
7. Produce reportes por categoría, perfil, overlap, y contribución marginal

## Pipeline Paso a Paso

### Paso 1: Sincronizar Firebog (descarga 150+ listas públicas)

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['sync-firebog']))"
```

**Output:**
- `config/sources.firebog.yml` - Catálogo auto-generado (do not edit manually)
- Console: resumen por categoría

**Resultado esperado:**
```
Fetching Firebog catalog...
  Found ~150 blocklists in Firebog
✓ Generated config/sources.firebog.yml with 150 sources
✓ Firebog sync complete
  suspicious: 30 lists
  advertising: 40 lists
  tracking: 35 lists
  malicious: 45 lists
  Total sources generated: 150
```

### Paso 2: Validar Configuración

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['validate']))"
```

**Output:**
```
✓ Config valid
  Sources: 151 (1 manual + 150 Firebog)
  Profiles: 7
  Policies precedence: malicious > tracking > advertising > suspicious > other > telemetry
```

### Paso 3: Construir Blocklists (Ingestar todos los dominios)

**IMPORTANTE:** Esta operación descarga y procesa millones de dominios (~30-60 minutos, ~2-5GB transferencia).

```bash
# Con fetch (descarga de red - puede tardar 30-60 min)
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build']))"

# Sin fetch (offline, solo archivos locales en caché - ~5 min)
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build', '--no-fetch']))"
```

**Output:**
```
✓ Unique domains: 2,500,000+ (ejemplo)
  Parsed OK: 2,800,000 | Sanitized OK: 2,500,000
  Reports: dist/reports/
  
Generated:
  - dist/all.txt (todos los dominios)
  - dist/categories/*.txt (por categoría: advertising, tracking, malicious, etc.)
  - dist/profiles/*.txt (por perfil: mobile, tv, strict, etc.)
  - dist/reports/stats.json (estadísticas)
  - dist/reports/provenance.json (mapping domain -> fuentes)
  - dist/reports/marginal.json (contribución única por fuente)
```

### Paso 4: Analizar Calidad

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['analyze']))"
```

**Output:**
```
✓ Analysis complete
  Total domains: 2,500,000
  Findings: 5
  High-discard sources: 2 (revisa drop_patterns)
  Overlap 2 sources: 150,000 (6%)
  Overlap 3+ sources: 80,000 (3.2%)
  Report: dist/reports/quality.md
```

**Revisa `dist/reports/quality.md` para:**
- Listas con altas tasas de descarte (posible formato incorrecto)
- Análisis de overlap (redundancia entre listas)
- Recomendaciones de consolidación

### Paso 5: Generar Recomendaciones

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['recommend']))"
```

**Output:**
```
✓ Recommendations generated
  Total domains: 2,500,000
  High-value sources: 45 (aportan >1% único o <20% overlap)
  Moderate-value sources: 50
  Low-value sources: 56 (=mayoritariamente overlap con otras)
  Top sources: [lista de las 5 mejores]
  Report: dist/reports/recommend.md
```

**Revisa `dist/reports/recommend.md` para:**
- Ranking de listas por valor (contribución única)
- Orden de carga recomendado (minimiza overlap)
- Porcentaje de dominios únicos vs. compartidos
- Sugerencias por región (España/Irlanda si tienes metadatos)

## Reports Generados

| Archivo | Contenido | Uso |
|---------|-----------|-----|
| `dist/all.txt` | Todos los dominios deduplicados | Carga en Pi-hole |
| `dist/categories/*.txt` | Listas por categoría | Segmentación por tipo |
| `dist/profiles/*.txt` | Listas por perfil (mobile, TV, strict) | Aplicar a grupos en Pi-hole |
| `dist/reports/stats.json` | Estadísticas: total, parsed, sanitized, descarte | Monitoreo |
| `dist/reports/provenance.json` | Mapping: dominio -> [fuentes que lo incluyen] | Auditoria, debugging |
| `dist/reports/marginal.json` | Fuente -> # dominios únicos en esa fuente | Decisión qué cargar |
| `dist/reports/quality.md` | Hallazgos: tasas descarte, overlap, anomalías | Control de calidad |
| `dist/reports/recommend.md` | Ranking de listas + orden carga óptimo | **Decisión final** |

## Cómo Cargar en Pi-hole v6

### Opción 1: GUI (Recomendado para inicio)

1. Accede a `http://pihole.local/admin` → **Adlists**
2. Copia URLs de `dist/reports/recommend.md` (Top sources)
3. Pega en "Enter a new adlist URL" y **Add**
4. Espera a que Pi-hole descargue y procese (observa el panel)
5. En **Group Management**, asigna listas a dispositivos/grupos según tus perfiles

### Opción 2: API/Script (Automatizado)

Pi-hole v6 expone una API SQLite:

```bash
# Obtener adlists actuales
curl -X GET "http://pihole.local/api/adlists" \
  -H "Authorization: Bearer YOUR_API_TOKEN"

# Añadir nueva adlist
curl -X POST "http://pihole.local/api/adlists" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"address": "https://raw.github.../all.txt", "description": "Factory-generated"}'

# Trigger gravity update
curl -X POST "http://pihole.local/api/gravity" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

Ver: https://docs.pi-hole.net/api/

### Opción 3: Carga manual en BD

```bash
# En el Pi-hole:
sqlite3 /etc/pihole/gravity.db

INSERT INTO adlist (address, description) 
VALUES ('https://tu-host/dist/all.txt', 'Factory-generated consolidated list');

-- O cargar por categoría/perfil:
INSERT INTO adlist (address, description) 
VALUES ('https://tu-host/dist/categories/advertising.txt', 'Factory-advertising');
INSERT INTO adlist (address, description) 
VALUES ('https://tu-host/dist/profiles/strict.txt', 'Factory-strict-profile');

-- Ejecutar gravity update:
pihole -g
```

**Importante:** No edites la DB manualmente en producción. Usa la GUI o la API.

## Customización

### Filtrar por Región (España/Irlanda)

**Opción 1: Crear perfil regional**

Edita `config/profiles.yml`:

```yaml
profiles:
  es_ie:
    name: "España & Irlanda"
    include_categories: [advertising, tracking, malicious]
    include_sources: [
      firebog_advertising_1,
      firebog_tracking_2,
      # ... añade IDs de fuentes específicas de ES/IE
    ]
    exclude_sources: []
```

Luego: `dist/profiles/es_ie.txt` contendrá solo listas regionales.

**Opción 2: Etiquetas manuales en `sources.local.yml`**

```yaml
sources:
  - id: my_es_regional
    name: "Regional ES blocklist"
    url: "https://ejemplo.es/blocklist.txt"
    category: advertising
    enabled: true
    notes: "Spanish regional - high-quality"
```

### Ajustar Sanitización

Edita `config/policies.yml`:

```yaml
policies:
  category_precedence: [malicious, tracking, advertising, suspicious, other, telemetry]
  core_domains:
    - apple.com
    - microsoft.com  # dominios NUNCA a bloquear
  base_allowlist:
    - google.com
  sensitive_domains: ~

# En inputs/current_overrides/:
# allowlist.txt - dominios a NUNCA bloquear
# denylist_extra.txt - dominios a SIEMPRE bloquear
# drop_patterns.txt - regex para descartar líneas en parse
```

### Añadir Nuevas Fuentes

**Manualmente:**

Crea/edita `config/sources.local.yml`:

```yaml
sources:
  - id: my_custom_list
    name: "Mi lista personalizada"
    url: "https://ejemplo.com/list.txt"
    category: advertising
    enabled: true
    tier: stable
```

**O desde archivo local:**

```yaml
sources:
  - id: local_file
    name: "Archivo local"
    url: "file://inputs/my_custom_list.txt"
    category: tracking
    enabled: true
```

## Troubleshooting

### Error: "High discard rate for source_X"

**Causa:** El parser no puede procesar el formato de esa lista.

**Solución:**
1. Revisa `dist/reports/quality.md`
2. Descarga manualmente la lista y verifica el formato (hosts, domain-only, ABP)
3. Añade regex a `inputs/current_overrides/drop_patterns.txt` para descartar líneas problemáticas
4. O desactiva esa fuente en `config/sources.local.yml`

### Error: Network timeout descargando listas

**Causa:** Red lenta o lista muy grande.

**Solución:**
1. Usa `--no-fetch` para reutilizar caché: `build --no-fetch`
2. Incrementa timeouts en `src/blocklist_builder/fetch.py` (parámetro `timeout_s`)
3. O descarga manualmente a `inputs/` y usa `file://` URLs

### Output dice 0 dominios después de build

**Causa:** Todas las líneas fueron descartadas en parse/sanitize.

**Solución:**
1. Revisa `dist/reports/stats.json` → "discarded" (qué razón prevalece)
2. Añade verbosidad o debug log
3. Verifica que `drop_patterns.txt` no sea demasiado agresivo

## Performance & Recursos

| Operación | Tiempo | Recursos | Notas |
|-----------|--------|----------|-------|
| `sync-firebog` | ~10s | <100MB | Descarga CSV + genera YAML |
| `validate` | <1s | <10MB | Solo lectura YAML |
| `build --fetch` | 30-60 min | 2-5GB down, 1GB temp | Descarga 150+ listas |
| `build --no-fetch` | 3-10 min | <500MB | Desde caché local |
| `analyze` | 1-5 min | <500MB | Lee JSON, calcula stats |
| `recommend` | 1-5 min | <500MB | Ranking algoritmo |
| Pi-hole gravity update | 5-15 min | Depends on Pi-hole HW | Con millones de dominios |

**Recomendación:** Ejecuta en máquina con >=4GB RAM libre.

## Flujo Sugerido (Primera Vez)

```bash
# 1. Setup
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['sync-firebog']))"

# 2. Test local (rápido)
export BLOCKLIST_SOURCES=test
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build', '--no-fetch']))"
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['analyze']))"
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['recommend']))"

# 3. Revisar reports de test
cat dist/reports/recommend.md

# 4. Full build con Firebog (toma tiempo)
unset BLOCKLIST_SOURCES
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['build']))" &
# ... mientras esperas, revisa

# 5. Una vez completado
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['analyze']))"
python3 -c "import sys; sys.path.insert(0, 'src'); from blocklist_builder.cli import main; sys.exit(main(['recommend']))"

# 6. Cargar en Pi-hole
# Copia URLs de dist/reports/recommend.md -> Pi-hole GUI
```

---

**Autor:** Blocklist Factory Generator
**Última actualización:** 2026-01-31
**Python:** 3.11+
**Dependencias:** PyYAML, requests
