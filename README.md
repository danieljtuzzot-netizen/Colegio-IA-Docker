# Colegio IA Docker

Demostración académica local de analítica docente e inteligencia artificial.
Integra dashboard, BETO, informatividad, MiniLM, consulta RAG, Ollama y la
opción vLLM con Qwen 1.5B. Está preparada para Windows con Docker Desktop,
contenedores Linux x86-64 y ejecución por CPU.

## Qué se entrega en GitHub

Código de ejecución, interfaz, Dockerfile, dependencias fijadas, composiciones,
lanzadores, comprobadores y documentación de instalación. Los datos
institucionales, checkpoints entrenados, pesos grandes, credenciales y tokens
no se versionan. El repositorio **no funciona sólo con clonarlo**: necesita
también los recursos autorizados descritos a continuación.

## Preparar los recursos privados

Solicitar al autor la entrega `Colegio_IA_Profesor_Windows_20261123.zip`
por el medio privado acordado. Su tamaño es aproximadamente 2,85 GB.
Extraerla y copiar **únicamente su carpeta `data`** a la raíz de esta copia
de GitHub. No reemplazar los archivos de código ni `ENTREGA_MANIFEST.json`.

La estructura debe quedar así:

```text
Colegio-IA-Docker/
  compose.ia.yaml
  scripts/ia/
  docker/ia/
  integracion_vllm/
  VLLM_15B_PC/
  data/ia/docker/demo_20261117_v1/
  data/ia/docker/ml_panel_20261117_v1/
```

`ENTREGA_MANIFEST.json` comprueba los hashes del código y de esos recursos.
El verificador avisará si falta un recurso o hay diferencias. No cambiar
hashes para omitir una comprobación. Los recursos incluyen el checkpoint
BETO ajustado, filtro, MiniLM, pesos de Ollama, índice RAG y derivados del
dashboard. No se necesita el corpus completo ni una base SQL.

## Instalar y ejecutar en Windows

1. Instalar [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
   con WSL 2 y contenedores Linux. Abrirlo y esperar al motor.
2. Descargar el código mediante **Code > Download ZIP** o clonar este repo.
3. Incorporar `data` siguiendo el apartado anterior.
4. En PowerShell dentro de esta carpeta ejecutar:

```powershell
.\VERIFICAR_ARCHIVOS.cmd
.\INICIAR_PROFESOR.cmd
```

Abrir [el dashboard local](http://127.0.0.1:8766/dashboard).
El laboratorio está en [la página principal](http://127.0.0.1:8766/).

La primera instalación necesita internet para imágenes y dependencias
públicas. No necesita XAMPP, MariaDB, Python del host, una cuenta de OpenAI,
GPU ni ngrok. La inferencia usa los modelos locales preparados.

## Opción vLLM 1.5B

La referencia probada fue un PC de **32 GB RAM**, con WSL configurado en
**20 GB**. Es una referencia de la prueba, no garantía para todo equipo.
El lanzador revisa memoria efectiva de Docker y arquitectura x86-64.
vLLM requiere instrucciones CPU AVX2 o AVX512. Reservar margen de disco para
imágenes, modelos y cachés; la guía propone 40 GB iniciales como planificación.

```powershell
.\INICIAR_VLLM_15B_PROFESOR.cmd
```

El modelo público `Qwen/Qwen2.5-1.5B-Instruct` se descarga con revisión
fijada y comprobación de hashes en el primer arranque. Sus pesos no están
en GitHub. Se reutilizan desde un volumen Docker al reiniciar.
Seleccionar vLLM en **Consultar con IA**.

## Comprobar y detener

Demo base:

```powershell
docker compose -f compose.ia.yaml exec demo python scripts/ia/probar_docker_ia.py --inferencia
```

Consulta vLLM:

```powershell
docker compose -f compose.ia.yaml -f compose.vllm.15b.integracion.yaml exec demo python scripts/ia/probar_integracion_vllm.py
```

Detener conservando datos y modelos:

```powershell
.\DETENER_PROFESOR.cmd
```

No usar `down -v` si se quieren conservar los volúmenes.
Las pruebas de respuesta y referencias son estructurales: contrastar también
el texto generado con sus comentarios de respaldo.

## Qué hace cada módulo

| Módulo | Función |
|---|---|
| Filtro y BETO | Separar informatividad y clasificar sentimiento. |
| Ridge exploratorio | Relacionar proporciones de sentimiento y promedio descriptivo del mismo periodo. |
| MiniLM y RAG | Recuperar evidencia mediante búsqueda semántica y palabras. |
| Ollama o vLLM | Ejecutar Qwen para selección y síntesis con referencias. |
| Dashboard | Explorar resultados congelados y consultar evidencia autorizada. |

El experimento ML comprende 173 casos de 103 docentes, con cinco grupos
de validación por docente. Su MAE visible es **4 pp**, la distancia media
redondeada entre promedio real y estimado en la escala porcentual. La
reducción de error **23 %** se calcula con métricas sin redondear frente al
control. No es un porcentaje de exactitud ni un pronóstico del próximo semestre.
El piloto RAG sólo consulta 22 comentarios autorizados, divididos en 41 segmentos.

## Alcance y estado

La demo base y la integración 1.5B se ejecutaron en el PC del autor durante
el desarrollo. Esta copia se prepara con comprobaciones de rutas, código,
secretos y hashes. El equipo que publica no dispone de Docker: hay que
construir y ejecutar las pruebas en el equipo del profesor para aceptarla.
No se activa producción, no se cambian notas ni se toman decisiones
automáticas sobre docentes. No incluye los datasets para repetir todo el
entrenamiento: requerirían autorización y una entrega de investigación aparte.

## Privacidad y derechos

Repositorio privado de entrega académica. No publicar `data`, revisiones,
SQL, credenciales ni los ZIP privados. La exclusión en Git no equivale a
anonimización. Los modelos y dependencias mantienen sus licencias originales.
No se concede una licencia abierta al proyecto mediante esta entrega.

Guía detallada: [LEEME_PROFESOR.txt](LEEME_PROFESOR.txt).
