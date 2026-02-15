# Performance Tuning Guide

**Objetivo**: Reducir el tiempo de procesamiento de millones de dominios de 30-60 minutos a <10 minutos.

## Optimizaciones Implementadas

### 1. Parallel HTTP Fetching
- **Antes**: Descargar 150+ listas secuencialmente (~30-40 min en red)
- **Despues**: ThreadPoolExecutor con concurrencia configurable
- **Impacto**: 4-6x mas rapido (~5-8 min)
- **Codigo**: `src/blocklist_builder/parallel.py::parallel_fetch_sources()`

```bash
# Controlar workers:
export BLOCKLIST_WORKERS=8  # Default: CPU_COUNT * 0.75
python3 run_build.py
```

### 2. Source-Level Parallel Processing
- **Antes**: Procesar cada fuente secuencialmente (una tras otra)
- **Despues**: ProcessPoolExecutor con un worker por fuente, todas en paralelo
- **Impacto**: Tiempo limitado por la fuente mas lenta, no por la suma de todas
- **Codigo**: `src/blocklist_builder/parallel.py::parallel_process_all_sources()`
- **Uso automatico**: Se activa con 3+ fuentes habilitadas

### 3. HTTP Caching + ETags
- **Antes**: Descargar todas las listas en cada build
- **Despues**: Cache con validacion ETag (skip 80-90% de descargas)
- **Impacto**: Segundo run: 1-2 min (solo diffs)
- **Codigo**: `src/blocklist_builder/fetch.py` con metadata JSON

### 4. Batch I/O Operations
- **Antes**: Write linea por linea
- **Despues**: Batch writes (write all, then flush)
- **Impacto**: 10-20% mas rapido
- **Codigo**: `build.py::_write_categories()`, `_write_profiles()`

## Benchmarks Esperados

### Escenario: ~40 fuentes, 3-5M lineas raw

| Fase | Antes | Despues | Speedup |
|------|-------|---------|---------|
| Fetch (red) | 25-35 min | 5-8 min | 4-6x |
| Parse + Sanitize | 8-12 min | 3-5 min | 2-3x |
| Deduplicacion | 2-3 min | 1-2 min | 2x |
| I/O + Reports | 1-2 min | 0.5-1 min | 2x |
| **Total** | **36-52 min** | **9-16 min** | **3-5x** |

### Escenario: Con cache (segundo run)

| Fase | Tiempo |
|------|--------|
| Fetch (skip 90%) | 1-2 min |
| Parse + Sanitize | 3-5 min |
| Total | **4-7 min** |

## Como Usar

### Build estandar
```bash
python3 run_build.py
```

### Tunar Workers
```bash
# Mas workers (servidores con muchos cores)
export BLOCKLIST_WORKERS=16
python3 run_build.py

# Menos workers (RAM limitado)
export BLOCKLIST_WORKERS=2
python3 run_build.py
```

### Incremental (sin red)
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from blocklist_builder.cli import main
sys.exit(main(['build', '--no-fetch']))
"
```

## Configuracion Recomendada por Caso

### Home Lab / Raspberry Pi (RAM limitado)
```bash
export BLOCKLIST_WORKERS=2
# Usado: ~512 MB
# Tiempo: 15-20 min
```

### Servidor (8+ cores, 32GB RAM)
```bash
export BLOCKLIST_WORKERS=12
# Usado: ~4 GB
# Tiempo: 8-12 min
```

### Docker / CI-CD
```bash
export BLOCKLIST_WORKERS=4
# Usado: ~1-2 GB
# Tiempo: 12-18 min
```

## Troubleshooting

### "Out of Memory"
```bash
export BLOCKLIST_WORKERS=1  # Desabilitar paralelismo
python3 run_build.py
```

### "Slow despite optimizations"
Causas probables:
- Disco lento (HDD vs SSD): esperado, 30-40 min en HDD
- Red lenta (<10 Mbps): esperado, 40-60 min
- CPU viejo (<4 cores): esperado, 20-30 min

## Notas Tecnicas

- **Threading vs Processes**: Fetch usa threads (I/O bound), parse usa processes (CPU bound)
- **GIL**: Python GIL limita parse secuencial; ProcessPoolExecutor lo evita
- **Scaling**: Mas alla de 16 workers, overhead de context switching > beneficio
- **Memoria**: El cuello de botella es `domain_to_categories` / `domain_to_sources` (~1-1.5 GB para 3M+ dominios), no el procesamiento paralelo

---

**Ultima actualizacion**: 2026-02-14
