def sql_insert_values(table_cols):
    """Genera la parte VALUES de un INSERT.
    
    Args:
        table_cols: Lista de tuplas (nombre_columna, tipo_sql)
    
    Returns:
        String con formato: " (col1, col2) VALUES (?, ?)"
    """
    return f" ({', '.join(col for col, _ in table_cols)}) VALUES ({', '.join(['?'] * len(table_cols))})"

def sql_create(table):
    """Genera la definición de una tabla para CREATE TABLE.
    
    Args:
        table: Lista de tuplas (nombre_columna, tipo_sql)
    
    Returns:
        String con formato: "col1 TYPE1, col2 TYPE2"
    """
    return f"{', '.join([f'{col} {type_}' for col, type_ in table])}"