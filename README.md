# Parser de Datos Tanita BC-601/BC-603 FS

Este script de Python lee los archivos CSV de la báscula Tanita BC-601/BC-603 FS y genera un reporte PDF con todas las mediciones organizadas y legibles.

## Características

- ✅ Lee archivos CSV de mediciones (DATA*.CSV) y perfiles (PROF*.CSV)
- ✅ Parsea el formato especial de Tanita (columnas alternadas header/valor)
- ✅ Genera reportes PDF profesionales con todas las mediciones
- ✅ Organiza los datos por importancia (peso, grasa, músculo, etc.)
- ✅ Soporta múltiples archivos y directorios
- ✅ Manejo de errores robusto

## Instalación

1. Instala las dependencias:
```bash
pip install -r requirements.txt
```

## Uso

### Opción 1: Procesar archivos específicos
```bash
python tanita_parser.py --files DATA1.CSV DATA2.CSV PROF1.CSV
```

### Opción 2: Procesar directorios completos
```bash
python tanita_parser.py --data-dir "TANITA/GRAPHV1/DATA" --system-dir "TANITA/GRAPHV1/SYSTEM"
```

### Opción 3: Buscar automáticamente en el directorio actual
```bash
python tanita_parser.py
```

### Opción 4: Especificar archivo de salida
```bash
python tanita_parser.py --output "mi_reporte_tanita.pdf"
```

## Parámetros disponibles

- `--files`: Archivos CSV específicos a procesar
- `--data-dir`: Directorio con archivos DATA*.CSV
- `--system-dir`: Directorio con archivos PROF*.CSV  
- `--output`: Nombre del archivo PDF de salida (por defecto: tanita_report.pdf)

## Datos de ejemplo

Para probar el script, puedes generar datos de ejemplo:

```bash
python generate_sample_data.py
python tanita_parser.py --data-dir sample_data
```

## Formato de los archivos CSV

Los archivos CSV de Tanita tienen un formato especial:
- Cada fila representa una medición
- Las columnas van en pares: header, valor, header, valor, ...
- Los headers son códigos de 2 caracteres (ej: "Wk", "MI", "FW")
- No hay encabezados tradicionales en la primera fila

### Ejemplo de formato:
```csv
"0","16","~0","cm","~1","kg","Wk","70.5","MI","22.1","DT","20231201","Ti","1430"
```

## Campos interpretados

El script reconoce y traduce los siguientes campos:

### Información básica
- **Wk**: Peso corporal (kg)
- **MI**: Índice de masa corporal (BMI)
- **DT**: Fecha de medición
- **Ti**: Hora de medición
- **GE**: Género
- **AG**: Edad
- **Hm**: Altura (cm)

### Composición corporal
- **FW**: Grasa corporal global (%)
- **Fr/Fl**: Grasa en brazos derecho/izquierdo (%)
- **FR/FL**: Grasa en piernas derecha/izquierda (%)
- **FT**: Grasa en torso (%)
- **mW**: Músculo global (%)
- **mr/ml**: Músculo en brazos derecho/izquierdo (%)
- **mR/mL**: Músculo en piernas derecha/izquierda (%)
- **mT**: Músculo en torso (%)
- **bw**: Masa ósea estimada (kg)

### Otros parámetros
- **ww**: Agua corporal global (%)
- **IF**: Grasa visceral
- **rA**: Edad metabólica estimada
- **rD**: Consumo calórico diario (DCI)
- **Bt**: Modo atleta (0=Normal, 2=Atleta)

## Salida del PDF

El reporte PDF incluye:
- Título y fecha de generación
- Resumen del total de mediciones
- Tabla organizada para cada medición con:
  - Campos importantes primero (peso, BMI, grasa global, etc.)
  - Grasa por región corporal
  - Músculo por región corporal
  - Otros parámetros
- Formato profesional con colores y estilos

## Solución de problemas

### Error: "No se encontraron mediciones"
- Verifica que los archivos CSV existan y tengan el formato correcto
- Asegúrate de que los archivos contengan datos de mediciones

### Error de codificación
- El script maneja automáticamente problemas de codificación
- Si persisten, verifica que los archivos no estén corruptos

### Error de dependencias
- Ejecuta `pip install -r requirements.txt` para instalar todas las dependencias

## Notas técnicas

- El script es compatible con Python 3.6+
- Utiliza ReportLab para la generación de PDFs
- Maneja automáticamente diferentes formatos de fecha/hora
- Preserva todos los datos originales, incluso campos desconocidos 