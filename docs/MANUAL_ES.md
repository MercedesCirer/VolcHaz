# Manual de usuario de VolcHaz

[English](USER_MANUAL_EN.md)

VolcHaz conecta tres etapas. En el preprocesamiento, combina posibles erupciones con condiciones atmosféricas históricas y conserva los escenarios que satisfacen las restricciones físicas. En el procesamiento, prepara y ejecuta ATLAS, un modelo de transporte y depósito de tefra. En el postprocesamiento, estima la amenaza para el conjunto de simulaciones y genera tablas, curvas y mapas. La configuración de Lascar se conserva para ilustrar el flujo de trabajo. Sus valores no son los parámetros usados en el trabajo original.

## 1. Instalación

En GitHub, elegí **Code → Download ZIP** y descomprimí el archivo, o cloná el repositorio. En Windows, abrí Anaconda Prompt. En macOS o Linux, abrí una terminal con Conda. Entrá en la carpeta que contiene `pyproject.toml`, reemplazando la ruta del ejemplo. Ejecutá los comandos del manual desde esa carpeta.

```text
cd "ruta/a/VolcHaz"
conda create -n volchaz python=3.13 pip
conda activate volchaz
python -m pip install -e ".[all]"
python -m pip check
python workflow/run.py --check
```

VolcHaz requiere Python 3.10 o posterior. Cada vez que abras otra terminal, volvé a ejecutar `conda activate volchaz`. La instalación editable toma el código de esta carpeta. `python -m pip install -r requirements.txt` instala el mismo conjunto de paquetes. NumPy y SciPy se usan para cálculos, pandas para tablas y Matplotlib para gráficos. El grupo `era5` agrega xarray, netCDF4 y cdsapi para los datos meteorológicos. `atlas` agrega netCDF4 y Paramiko para leer resultados y conectarse por SSH. `mapping` agrega netCDF4, GeoPandas, Shapely, pyproj y Cartopy para mapas. Si solo vas a preprocesar, podés instalar `python -m pip install -e ".[era5]"`. Las versiones requeridas están en `pyproject.toml`.

### Conexión a Climate Data Store (CDS)

1. Creá una cuenta o iniciá sesión en Climate Data Store. En la página de la API, copiá la URL y el token personal de tu cuenta. Si no instalaste los grupos `era5` o `all`, ejecutá `python -m pip install "cdsapi>=0.7"`. [Configuración oficial de CDS](https://cds.climate.copernicus.eu/how-to-api)
2. Guardá un archivo de texto llamado `.cdsapirc` en tu carpeta de usuario. En Windows es `%USERPROFILE%\.cdsapirc`. Verificá que el editor no le haya agregado `.txt`. En macOS o Linux es `~/.cdsapirc`. Sustituí el texto de ejemplo por tu token. Guardá el archivo fuera de VolcHaz.

   ```yaml
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_PERSONAL_ACCESS_TOKEN
   ```
3. Con la sesión iniciada, entrá a la pestaña de descarga del producto ERA5 en niveles de presión y aceptá sus condiciones de uso. Para preparar la meteorología de ATLAS, aceptá también las del producto de niveles únicos. La aceptación se hace por producto. [ERA5 en niveles de presión](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels?tab=download) · [ERA5 en niveles únicos](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download)
4. Ejecutá el paso 02 de preprocesamiento para enviar las solicitudes. En **Your requests**, CDS muestra si la descarga está en cola. Si aparece un error de autorización, revisá la URL, el token y las condiciones de uso. Si se corta la descarga, podés repetir el paso con `ERA5_OVERWRITE=False` para reutilizar los archivos legibles.

### Instalación de ecCodes y ATLAS

En la computadora que descargará la meteorología completa para ATLAS, instalá ecCodes en el entorno activo con `conda install -c conda-forge eccodes`. Ejecutá `grib_to_netcdf -V` para comprobar que quedó disponible. Si el conversor se instaló en otro lugar, indicá la ruta del ejecutable en `ATLAS_GRIB_TO_NETCDF_EXECUTABLE`. Necesitás una distribución que incluya el conversor con soporte NetCDF. [Paquete ecCodes](https://github.com/conda-forge/eccodes-feedstock) · [Documentación del conversor](https://confluence.ecmwf.int/spaces/ECC/pages/45747871/grib_to_netcdf)

ATLAS se instala por separado en el servidor donde se harán las simulaciones. Pedile al administrador acceso SSH, recursos de ejecución y la ruta de una versión compatible con las entradas ERA5 de VolcHaz. Si vas a compilar ATLAS-1.0, consultá su manual y repositorio. Necesita una implementación de MPI, como Open MPI o MPICH, un compilador Fortran compatible con MPI, NCO, NetCDF-Fortran, Python 3 y make. Configurá el Makefile para el servidor, ejecutá `make` en la carpeta principal de ATLAS y localizá `Runs/P_ATLAS.1.0.x`. Usá la demostración que distribuye ATLAS para comprobar el ejecutable y sus bibliotecas antes de conectar VolcHaz. [Código e instalación de ATLAS-1.0](https://github.com/ATLASFlor/ATLAS-1.0)

## 2. Estructura y archivos que se editan

```text
VolcHaz/
├── README.md, LICENSE, pyproject.toml, requirements.txt
├── docs/                        Manual en español e inglés
├── workflow/
│   ├── run.py                   Menú y ejecuciones por número de paso
│   ├── atlas_points.csv          Ubicaciones para el análisis puntual
│   ├── preprocessing/
│   │   ├── configs/preprocessing_config.py
│   │   ├── configs/multiphase_example.txt
│   │   └── pasos 01–10 y run_all.py
│   ├── processing/
│   │   ├── configs/processing_config.py
│   │   └── pasos 01–04 y run_all.py
│   └── postprocessing/
│       ├── configs/postprocessing_config.py
│       └── pasos 01–06 y run_all.py
├── src/volcanic_toolbox/         Implementación en Python
├── data/                       Datos ERA5 y cartografía incorporados al trabajar
└── outputs/<SCENARIO_NAME>/      Resultados generados por etapa
```

Abrí los tres archivos `*_config.py` con un editor de texto. Cambiá el valor a la derecha de `=` o `:`. Conservá los nombres de las variables, las comas, los corchetes y las comillas de los textos. Usá punto para los decimales y escribí `True`, `False` y `None` tal como aparecen. Las líneas que empiezan con `#` explican qué significa cada valor. Si trabajás con ubicaciones puntuales, también podés editar `workflow/atlas_points.csv`. Ejecutá `python workflow/run.py --check` después de editar para revisar la sintaxis y la coherencia entre etapas. Esta verificación es local. `python workflow/run.py` abre el menú interactivo. También podés suministrar la etapa y el número de paso en el comando.

## 3. Preprocesamiento — preparar los escenarios aceptados

Editá [preprocessing_config.py](../workflow/preprocessing/configs/preprocessing_config.py). Con `SCENARIO_TYPE='monophase'`, se usa `MONOPHASE_SCENARIO`. Para más de una fase, copiá toda la asignación `MULTIPHASE_SCENARIO = {...}` de [multiphase_example.txt](../workflow/preprocessing/configs/multiphase_example.txt) a la sección B de ese mismo archivo Python y seleccioná `SCENARIO_TYPE='multiphase'`. Los nombres de las fases deben coincidir en `PHASES` y `PHASE_METEOROLOGY`.

- `SCENARIO_NAME` define el nombre de las carpetas de datos y resultados. `LATITUDE` y `LONGITUDE` van en grados decimales, con valores negativos hacia el sur y el oeste. `VENT_ELEVATION_M` es la cota de la boca eruptiva en metros sobre el nivel del mar. `COLUMN_HEIGHT_REFERENCE` indica si la altura de columna se mide sobre la boca (`above_vent`) o sobre el nivel del mar (`asl`).
- `YEARS` incluye el primer y el último año. En cada fase elegí `pressure_level_hpa` y `source`. `historical` usa todo el registro preparado. `tmy` elige meses representativos del registro histórico mediante `TMY_SETTINGS`, según su concordancia en velocidad y dirección del viento. Las fechas seleccionadas conservan sus marcas de tiempo históricas para el forzamiento de ATLAS. `ERA5_HALF_BOX_DEGREES` indica la mitad del ancho del recuadro alrededor del volcán y `ERA5_TIMES_UTC` determina las horas de observación. `N_METEOROLOGY_SAMPLES` y `METEOROLOGY_SAMPLE_SETTINGS` controlan cantidad, semilla y muestreo con o sin reemplazo.
- En `PHASES`, configurá la altura de columna, duración equivalente, granulometría y agregación. Conservá claves como `column_height` y `duration`. Seleccioná en conjunto la `distribution`, sus `parameters` y los límites admisibles `bounds`. La duración equivalente indica el tiempo de emisión de la fase modelada. `TGSD_MIN_PHI` y `TGSD_MAX_PHI` fijan los límites granulométricos. Los valores phi menores corresponden a partículas más gruesas.
- `EVENT_VEI` identifica la clase de explosividad. Definí `MINIMUM_FALLOUT_VOLUME_KM3`, `MAXIMUM_FALLOUT_VOLUME_KM3` y `BULK_DENSITY_KG_M3` para acotar la masa del depósito de caída. VolcHaz estima la tasa de descarga de masa, o MER, en kg/s a partir de las condiciones de columna y viento y la multiplica por la duración en segundos. En un caso multifásico, la restricción del evento se aplica a la suma de las masas de las fases. `SCENARIO_BUILD_SETTINGS` controla cuántos escenarios se aceptarán, el tamaño de lote, el límite de intentos, la semilla y el emparejamiento con reemplazo. `SEASONS` identifica estaciones para los resúmenes de esta etapa.

Como referencia, Lascar usa `pressure_level_hpa=50` para la fase `eruption`, `YEARS=(2010, 2020)` y un objetivo de 1.000 escenarios aceptados con volúmenes de caída entre 0,08 y 0,12 km³. Una distribución uniforme requiere `low` y `high`. Una triangular usa `left`, `mode` y `right`. Una normal usa `mean` y `std`, y un valor fijo usa `value`. La lognormal usa por defecto `mu` y `sigma` en escala logarítmica. Los campos opcionales `minimum` y `maximum` de `bounds` limitan el muestreo antes del filtro físico.

En una copia recién descargada, ejecutá los siguientes pasos. El 02 guarda un NetCDF por año y fase en `data/era5/<SCENARIO_NAME>/<phase>/`. Con datos compatibles ya guardados, podés empezar en el 03. Dejá en la carpeta de cada fase solo los NetCDF del período, nivel, área y horarios seleccionados. Si cambiás esas condiciones, usá otro `SCENARIO_NAME` o reemplazá los archivos que dejaron de corresponder a tu configuración.

```text
python workflow/run.py preprocessing 02
python workflow/run.py preprocessing 03
python workflow/run.py preprocessing 04
python workflow/run.py preprocessing 06
python workflow/run.py preprocessing 10
```

El paso 03 guarda la serie de viento cerca del volcán en `full_wind_data.csv` y, si corresponde, los diagnósticos del TMY. El 04 escribe `selected_meteorology_samples.csv`. El 06 guarda escenarios aceptados, combinaciones evaluadas y un resumen en `outputs/<SCENARIO_NAME>/preprocessing/scenarios/`. Revisá la cantidad aceptada y el intervalo de volúmenes. Si se alcanza el límite de intentos, revisá primero los supuestos físicos y los límites de muestreo para decidir si corresponde aumentar `max_attempts`. El 10 muestra cómo quedaron asociadas las fechas y condiciones meteorológicas a las fases.

Los pasos optativos son 01 (histogramas de candidatos), 05 (rosas de viento anual y mensuales), 07 (gráficos de pares de variables), 08 (comparación de vientos antes y después de la selección) y 09 (histogramas de parámetros candidatos frente a los aceptados, requiere los pasos 01 y 06). `python workflow/run.py preprocessing all` corre 03, 04 y 06, más los pasos seleccionados con `DOWNLOAD_METEOROLOGY` y las opciones `RUN_*`. Si `RUN_PARAMETER_COMPARISON=True`, también ejecuta el 01. El paso 10 se ejecuta por separado. [Referencia de scripts de preprocesamiento](../workflow/preprocessing/SCRIPT_GUIDE.md)

## 4. Procesamiento — preparar la meteorología, generar entradas y ejecutar ATLAS

Editá [processing_config.py](../workflow/processing/configs/processing_config.py). El nombre del escenario, las fases y sus fechas se heredan del preprocesamiento.

1. Definí `ATLAS_AREA` en el orden (norte, oeste, sur, este) y `ATLAS_DAYS_AFTER` para abarcar el período de transporte. El día de inicio más cinco días posteriores cubre seis días calendario. Esta etapa usa campos ERA5 completos de niveles de presión y niveles únicos. Los vientos del preprocesamiento sirvieron para seleccionar los escenarios.
2. Ejecutá `python workflow/run.py processing 01` con `ATLAS_DRY_RUN=True` para revisar el plan en `outputs/<SCENARIO_NAME>/processing/atlas/manifests/`. Después ponelo en `False` y repetí el 01 para descargar, convertir y unir los datos en archivos `YYYYMMDD.era5.nc` bajo `atlas/era5/`. Empezá con `ATLAS_MAX_WORKERS=1`. Si ya se convirtieron los bloques y se interrumpió su unión, ejecutá `python workflow/run.py processing 02`.
3. Indicá en `ATLAS_INSTALL_BASE` la carpeta remota que contiene la instalación, en `ATLAS_DIRECTORY_NAME` el nombre de esa instalación y en `REMOTE_ATLAS_ROOT` la ruta absoluta que combina ambas. Confirmá `ATLAS_VOLCANO_NAME` y revisá `ATLAS_MAIN_INPUT` (tope, resolución, paso de integración e intervalo entre salidas), `ATLAS_NUMBER_PARTICLES`, `ATLAS_MASS_FLOW_RATE`, los parámetros de la fuente y las propiedades de partículas según tu versión de ATLAS. Usá `ATLAS_REQUIRE_LOCAL_METEOROLOGY=True` para generar entradas que se van a simular. Ejecutá `python workflow/run.py processing 03` y revisá el manifiesto `atlas/inputs/atlas_input_manifest.csv` y los archivos principales y de fase `.inp`.
4. Indicá `SSH_HOST`, `SSH_PORT`, `SSH_USER` y `REMOTE_ATLAS_EXECUTABLE`. Confirmá con el administrador la huella de la clave del servidor y conectate una vez con `ssh -p PUERTO USUARIO@SERVIDOR` para guardar la clave verificada en el archivo local `known_hosts`. Conservá `SSH_HOST_KEY_POLICY='reject'`. Para autenticarte, usá un agente SSH o indicá en `SSH_PRIVATE_KEY` la ruta de tu clave. Si el servidor requiere contraseña, colócala en la variable de entorno local indicada por `SSH_PASSWORD_ENV_VAR` (por defecto, `ATLAS_SSH_PASSWORD`). Guardá la contraseña fuera de los archivos del proyecto.
5. Ajustá `MPI_PROCESSES`, `REMOTE_SHELL_PREAMBLE` y `LAUNCH_COMMAND_TEMPLATE` a los recursos asignados. El programa sustituye `{mpi_processes}`, `{executable}`, `{date}` y `{run_dir}`. En un clúster con cola de trabajos, usá el mecanismo indicado por el administrador y asegurate de que el comando espere a que termine ATLAS. Revisá `SKIP_MISSING_METEOROLOGY`, `ACCEPT_NONEMPTY_PART_ON_FAILED_EXIT`, `CLEANUP_REMOTE_SIMULATION` y `AUTO_DELETE_UNUSED_REMOTE_METEO`. Las dos últimas opciones controlan la eliminación remota de las simulaciones y del forzamiento que ya no se necesita.
6. Corré `python workflow/run.py processing 04` con `ATLAS_REMOTE_DRY_RUN=True` para verificar la conexión y las rutas. Cuando la verificación sea satisfactoria, ponelo en `False` y repetí el 04 para transferir archivos, correr ATLAS y recuperar las salidas. Confirmá que estén los archivos `*.part.nc` bajo `outputs/<SCENARIO_NAME>/processing/atlas/runs/<phase>/<run_folder>/`. El flujo puede reutilizar salidas locales completas. Para otra versión del modelo o del conjunto de simulaciones, usá una carpeta de escenario nueva para evitar mezclar resultados.

`python workflow/run.py processing all` encadena los pasos 01, 03 y 04. [Referencia de scripts de procesamiento](../workflow/processing/SCRIPT_GUIDE.md)

Si usás una contraseña, estos comandos la piden sin incluirla en el texto del comando. Ejecutalos en la misma terminal activada que usarás para el paso 04. Después podés borrar la variable temporal con `Remove-Item Env:ATLAS_SSH_PASSWORD` en PowerShell o `unset ATLAS_SSH_PASSWORD` en Bash.

**PowerShell 7**

```powershell
$env:ATLAS_SSH_PASSWORD = Read-Host -MaskInput "Contraseña SSH de ATLAS"
```

**Bash**

```bash
read -r -s -p "Contraseña SSH de ATLAS: " ATLAS_SSH_PASSWORD
export ATLAS_SSH_PASSWORD
```

## 5. Postprocesamiento — estimar y representar la amenaza

Editá [postprocessing_config.py](../workflow/postprocessing/configs/postprocessing_config.py). Podés empezar con `python workflow/run.py postprocessing 02` para inspeccionar hasta cinco archivos de ATLAS. En `ATLAS_POSTPROCESS_CONFIG`, definí `c3d_thresholds_kg_m3` para concentración en el aire, `gl_thresholds_kg_m2` para carga final sobre el suelo, `altitude_ranges` para intervalos nombrados en metros sobre el nivel del mar y los operadores verticales. Definí `arrival_hours`, `persistence_hours` y `dt_hours`. Este último debe coincidir con el intervalo entre salidas `output_frequency_h`. Cada entrada de `month_groups` identifica un subconjunto de meses de inicio de las simulaciones. Si querés usar las mismas estaciones en todo el flujo, sincronizá esos grupos con `SEASONS`.

`probability_comparison` permite elegir si la excedencia incluye o excluye la igualdad con el umbral. Las probabilidades de concentración y carga describen la fracción de simulaciones que cumple los criterios definidos. La llegada expresa la probabilidad de que la primera excedencia ocurra hasta la hora indicada. La persistencia corresponde al período continuo de excedencia tras la primera llegada. Su versión condicional toma como denominador las simulaciones con excedencia, mientras que la incondicional usa todas las simulaciones que contribuyen al cálculo. Revisá los tamaños de muestra y los archivos inválidos, en especial si `skip_invalid_files=True`. VolcHaz expresa las probabilidades en porcentajes para el conjunto seleccionado. Para interpretarlas como probabilidades anuales, se necesita un modelo adicional de frecuencia eruptiva.

Configurá `ATLAS_INDEX_CONFIG` y `PROBABILITY_CUTOFF_PERCENT` para las clases de amenaza. Los umbrales y tiempos pedidos por un índice o mapa deben existir entre las salidas calculadas. En casos multifásicos, los índices combinan clases ordinales con reglas y pesos explícitos, sin representar una probabilidad conjunta ni una suma física de concentraciones. Para ubicaciones puntuales, editá [atlas_points.csv](../workflow/atlas_points.csv) con el encabezado `point_id,latitude,longitude` o definí `inline_points`. En `point_extraction` podés elegir la celda más cercana o la ponderación por distancia inversa. Para omitir puntos, usá `point_table=None` e `inline_points=()`.

```text
python workflow/run.py postprocessing 01
python workflow/run.py postprocessing 04
python workflow/run.py postprocessing 05
python workflow/run.py postprocessing 06
```

El paso 01 escribe probabilidades en NetCDF bajo `outputs/<SCENARIO_NAME>/postprocessing/atlas/<phase>/<subset>/probability_fields/` y guarda el manifiesto y la configuración en `postprocessing/atlas/`. También puede generar índices y resultados puntuales. Si solo cambian las coordenadas o la interpolación de los puntos, el paso 03 vuelve a extraerlos de las grillas existentes. El paso 04 resume la tabla de puntos y revisa la consistencia de las curvas. El 05 grafica los grupos que superan `MIN_PROBABILITY_TO_PLOT_PERCENT`. Corré estos pasos de curvas cuando ya tengas las salidas de puntos.

Para el paso 06, descargá **Admin 0 – Countries** 1:10m de Natural Earth y descomprimí sus componentes juntos en `data/basemaps/global/`. El valor original de `BASEMAP_SHP` busca allí `ne_10m_admin_0_countries.shp`, que debe estar acompañado por los archivos `.dbf`, `.shx` y `.prj`. Configurá los productos en `C3D`, `GL`, `AT`, `PT_CONDITIONAL` y `PT_UNCONDITIONAL`. Cada producto acepta `extent` en el orden (oeste, este, sur, norte), o `None` para heredar el encuadre general. La extensión afecta el área mostrada. Usá `BASE_CONFIG` para la interpolación, `OUTPUT_CONFIG` para los archivos y `MAP_CONFIG` para el umbral de visualización. El archivo `stage6_mapping_manifest.csv` registra qué mapas se generaron. [Descarga de Natural Earth](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/)

`python workflow/run.py postprocessing all` ejecuta 01 y 06. Si cambian umbrales, intervalos de altura o subconjuntos del ensamble, repetí el 01. Si solo ajustás el aspecto del mapa, repetí el 06. Para un estudio científico, guardá junto a los resultados la configuración, las semillas, las versiones del modelo y los paquetes, el registro del forzamiento y los manifiestos. [Referencia de scripts de postprocesamiento](../workflow/postprocessing/SCRIPT_GUIDE.md) · [Referencia de configuración](../workflow/CONFIGURATION.md)
