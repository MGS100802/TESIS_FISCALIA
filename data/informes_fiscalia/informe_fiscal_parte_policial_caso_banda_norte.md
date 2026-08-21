**MINISTERIO PÚBLICO / FISCALÍA**
**UNIDAD DE ANÁLISIS CRIMINAL Y FOCOS INVESTIGATIVOS**

**MEMORÁNDUM INTERNO: INFORME DE INTELIGENCIA CRIMINAL**
**A:** Fiscal Adjunto a Cargo
**DE:** Asesoría en Inteligencia Criminal y Derecho Procesal Penal
**REF:** Informe de Inteligencia y Propuesta de Persecución Penal (RUC: parte_policial_caso_banda_norte)

---

### 1. ANTECEDENTES Y SÍNTESIS DE LA INVESTIGACIÓN
La presente investigación se centra en una estructura criminal organizada con presencia consolidada en la zona norte de la Región Metropolitana. De acuerdo con los antecedentes recopilados, la organización se dedica al robo con violencia, intimidación y la receptación de vehículos motorizados, operando bajo un esquema de asociación ilícita. La investigación se ha elevado tras la aplicación de técnicas de modelamiento de grafos, permitiendo identificar un núcleo duro de 13 sujetos que articulan el actuar delictivo.

### 2. ANÁLISIS DE RED Y METODOLOGÍA MATEMÁTICA
La identificación de los integrantes se realizó mediante la arquitectura de procesamiento multi-agente, aplicando un *Filtro Directo Demo* que permitió reducir un universo inicial de 77 sospechosos a un subgrafo de 13 nodos, con una **Propensión Criminal Generativa (PCG)** promedio de 0.904, significativamente superior al resto de la red (0.387).

La validación técnica, realizada mediante optimización matemática (StRAM/Gurobi), confirma que la red posee un alto nivel de conectividad interna (densidad: 0.256; clustering: 0.41), lo que garantiza la operatividad de la banda. El modelo ha verificado que esta estructura es un componente único y conexo, validando su naturaleza jerárquica y colaborativa.

### 3. ESTRUCTURA Y ROLES DE LA ORGANIZACIÓN CRIMINAL
El análisis de los 13 integrantes detectados permite inferir una jerarquía basada en la *betweenness centrality* (centralidad de intermediación):

*   **Núcleo de Comando y Control (HVT):** Sujetos 6 y 77. Presentan los mayores índices de centralidad y una PCG de 1.0, lo que los posiciona como los coordinadores operativos y logísticos.
*   **Operativos de Enlace:** Sujetos 67 y 58, quienes mantienen la cohesión del subgrafo y actúan como puentes en la cadena de mando.
*   **Ejecutores y Soporte:** Sujetos restantes (1, 3, 26, 37, 41, 51, 66, 71, 75). Estos presentan un PCG de 1.0, indicando una alta peligrosidad individual, aunque su rol es tácticamente subordinado a los nodos centrales.

### 4. ESTRATEGIA DE DESARTICULACIÓN E INTERDICCIÓN TÁCTICA
El modelo de optimización ha determinado que la captura del **HVT (ID: 6)** es el punto crítico para la neutralización de la banda. La remoción de este nodo provoca:
1.  Una **caída del 23.35% en la conectividad global** de la banda.
2.  La fragmentación del grupo en al menos **2 componentes desconectadas**, lo que impide la continuidad operativa de la asociación ilícita.

Se recomienda priorizar la interdicción sobre los sujetos 6, 77 y 67, dado que concentran la mayor capacidad de resiliencia delictual de la estructura.

### 5. SOLICITUD DE DILIGENCIAS INVESTIGATIVAS AL FISCAL
Considerando la evidencia técnica de la estructura, se solicita al Fiscal Adjunto gestionar ante el Juzgado de Garantía respectivo las siguientes actuaciones:

1.  **Medidas Intrusivas:** Solicitar orden judicial de interceptación y monitoreo de comunicaciones para los IDs 6, 77, 67 y 58, a fin de establecer la cadena de mando y coordinaciones logísticas actuales.
2.  **Entrada y Registro:** Autorización para el ingreso a los domicilios identificados de los HVTs (6 y 77) para la incautación de evidencia (teléfonos, armas, y bienes provenientes de receptación).
3.  **Ordenes de Detención:** Proponer el desarrollo de una fase operativa sincronizada una vez finalizada la etapa de interceptación, enfocada en la desarticulación simultánea de los nodos de alta centralidad.
4.  **Inmovilización:** Oficiar a las entidades financieras y registros públicos para la trazabilidad de bienes y activos asociados a los sujetos 6 y 77 para futuras solicitudes de medidas cautelares reales.

**Atentamente,**

*Asesoría en Inteligencia Criminal*
*Unidad de Análisis Criminal y Focos Investigativos*