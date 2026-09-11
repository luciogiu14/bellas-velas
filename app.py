import streamlit as st
import sqlite3
import pandas as pd
import math

# Intentar importar st_keyup para filtrado instantáneo tecla por tecla
try:
    from st_keyup import st_keyup
    USA_KEYUP = True
except ImportError:
    USA_KEYUP = False

st.set_page_config(page_title="Bellas Velas - Gestión", page_icon="🕯️", layout="wide")

# =========================================================
# CONTROL DE ACCESO / CONTRASEÑA
# =========================================================
# CAMBIÁ ESTA CONTRASEÑA POR LA QUE VOS QUIERAS:
CLAVE_CORRECTA = "marie2026"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def check_password():
    if not st.session_state.autenticado:
        st.write("")
        st.write("")
        c_vacio1, c_login, c_vacio2 = st.columns([1, 2, 1])
        with c_login:
            st.markdown("## 🔒 Bellas Velas - Acceso Seguro")
            st.caption("Ingresá la contraseña para acceder al sistema de gestión.")
            with st.form("form_login"):
                password_input = st.text_input("Contraseña:", type="password", placeholder="Escribí la clave...")
                boton_ingresar = st.form_submit_button("Ingresar al Sistema 🔑", use_container_width=True)
                
                if boton_ingresar:
                    if password_input == CLAVE_CORRECTA:
                        st.session_state.autenticado = True
                        st.rerun()
                    else:
                        st.error("❌ Contraseña incorrecta. Intentá nuevamente.")
        return False
    return True

# Si no está logueado, se detiene acá y no muestra nada de la app
if not check_password():
    st.stop()

# Botón lateral para cerrar sesión si se desea
with st.sidebar:
    st.caption("Sesión activa")
    if st.button("Cerrar Sesión 🚪", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# =========================================================
# CONEXIÓN A BASE DE DATOS Y CONFIGURACIÓN INICIAL
# =========================================================
DB_NAME = "bellas_velas.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Asegurar columna nro_ticket en ventas
    cursor.execute("PRAGMA table_info(ventas)")
    cols_v = [col[1] for col in cursor.fetchall()]
    if "nro_ticket" not in cols_v and len(cols_v) > 0:
        cursor.execute("ALTER TABLE ventas ADD COLUMN nro_ticket INTEGER DEFAULT 1")
        conn.commit()
        
    # Asegurar existencia de ítem REFILL en productos
    refill_prod = cursor.execute("SELECT 1 FROM productos WHERE id_producto = 'REFILL'").fetchone()
    if not refill_prod:
        cursor.execute("""
        INSERT INTO productos (id_producto, nombre, tipo_linea, gramos_cera, costo_recipiente_o_molde, costo_fabricacion, precio_venta_sugerido, precio_venta_actual, stock_minimo_alerta, stock_actual)
        VALUES ('REFILL', 'Servicio de Refill / Recarga de Vela', 'Accesorio', 0, 0, 0, 0, 0, 0, 99999)
        """)
        conn.commit()
        
    # Asegurar configuración de margen de refill en insumos
    margen_ref = cursor.execute("SELECT 1 FROM insumos WHERE id_insumo = 'CFG-MARGEN-REF'").fetchone()
    if not margen_ref:
        cursor.execute("""
        INSERT INTO insumos (id_insumo, nombre, categoria, unidad_medida, costo_unitario)
        VALUES ('CFG-MARGEN-REF', 'MULTIPLICADOR MARGEN REFILL', 'Config', 'ratio', 3.0)
        """)
        conn.commit()
        
    return conn

st.title("🕯️ Bellas Velas - Control de Stock y Ventas")

# Pestañas principales
tab_consulta, tab_stock, tab_ventas, tab_historial, tab_config = st.tabs([
    "🔍 Consultar Precios y Stock",
    "📦 Ingreso de Stock / Catálogo",
    "🛒 Registrar Venta",
    "📊 Historial de Ventas",
    "⚙️ Insumos y Precios"
])

# Inicializar estados de la sesión
if "carrito" not in st.session_state:
    st.session_state.carrito = []
if "reset_repo" not in st.session_state:
    st.session_state.reset_repo = 0
if "reset_nuevo" not in st.session_state:
    st.session_state.reset_nuevo = 0
if "reset_mod" not in st.session_state:
    st.session_state.reset_mod = 0
if "item_selector_key" not in st.session_state:
    st.session_state.item_selector_key = 0

# =========================================================
# TAB 1: CONSULTA RÁPIDA (Filtro instantáneo tecla por tecla)
# =========================================================
with tab_consulta:
    st.subheader("Buscador de Precios, Costos y Stock")
    
    col_b1, col_b2 = st.columns([4, 2])
    with col_b1:
        if USA_KEYUP:
            busqueda = st_keyup(
                "Buscar producto (escribí código o nombre):",
                placeholder="Ej: 001, burbuja, whisky, apagador...",
                debounce=200,
                key="busqueda_keyup"
            )
        else:
            busqueda = st.text_input(
                "Buscar producto (escribí código o nombre):",
                placeholder="Ej: 001, burbuja, whisky, apagador...",
                key="busqueda_normal"
            )
            
    with col_b2:
        filtro_linea = st.selectbox("Filtrar por línea:", ["Todas", "Recipiente", "Molde", "Accesorio"])
        
    conn = get_connection()
    query = """
    SELECT id_producto AS Código, nombre AS Descripción, tipo_linea AS Línea,
           gramos_cera AS [Grs Cera],
           costo_recipiente_o_molde AS [Costo Envase ($)],
           costo_fabricacion AS [Costo Fab. ($)],
           precio_venta_sugerido AS [Precio Sugerido ($)],
           precio_venta_actual AS [Precio Venta ($)],
           stock_actual AS [Stock Disp.],
           stock_minimo_alerta AS [Stock Mín.]
    FROM productos
    WHERE id_producto != 'REFILL'
    """
    params = []
    if busqueda and busqueda.strip():
        query += " AND (id_producto LIKE ? OR nombre LIKE ?)"
        term = f"%{busqueda.strip()}%"
        params.extend([term, term])
    if filtro_linea != "Todas":
        query += " AND tipo_linea = ?"
        params.append(filtro_linea)
        
    query += " ORDER BY tipo_linea, nombre"
    
    df_prod = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df_prod.empty:
        st.info("No se encontraron productos con ese criterio de búsqueda.")
    else:
        def alerta_precio(row):
            sugerido = row["Precio Sugerido ($)"] or 0
            venta = row["Precio Venta ($)"] or 0
            if sugerido > 0 and venta < sugerido:
                dif = sugerido - venta
                return f"⚠️ Menor al sugerido (-${dif:,.0f})"
            elif sugerido > 0:
                return "✅ Óptimo"
            else:
                return "⚪ Sin calcular"
                
        def semaforo_stock(row):
            stock = row["Stock Disp."]
            minimo = row["Stock Mín."]
            if stock <= 0:
                return "🔴 Sin Stock"
            elif stock <= minimo:
                return "🟡 Stock Bajo"
            else:
                return "🟢 Disponible"
                
        df_prod["Alerta Precio"] = df_prod.apply(alerta_precio, axis=1)
        df_prod["Estado Stock"] = df_prod.apply(semaforo_stock, axis=1)
        
        df_prod["Costo Envase ($)"] = df_prod["Costo Envase ($)"].apply(lambda x: f"${x:,.0f}")
        df_prod["Costo Fab. ($)"] = df_prod["Costo Fab. ($)"].apply(lambda x: f"${x:,.0f}")
        df_prod["Precio Sugerido ($)"] = df_prod["Precio Sugerido ($)"].apply(lambda x: f"${x:,.0f}")
        df_prod["Precio Venta ($)"] = df_prod["Precio Venta ($)"].apply(lambda x: f"${x:,.0f}")
        df_prod["Grs Cera"] = df_prod["Grs Cera"].apply(lambda x: f"{x:,.0f} g" if x > 0 else "-")
        
        columnas_ordenadas = [
            "Código", "Descripción", "Línea", "Grs Cera",
            "Costo Envase ($)", "Costo Fab. ($)", "Precio Sugerido ($)",
            "Precio Venta ($)", "Alerta Precio", "Stock Disp.", "Estado Stock"
        ]
        
        st.dataframe(df_prod[columnas_ordenadas], use_container_width=True, hide_index=True)

# =========================================================
# TAB 2: INGRESO DE STOCK / GESTIÓN DE CATÁLOGO
# =========================================================
with tab_stock:
    st.subheader("Gestión de Modelos y Stock")
    tipo_accion = st.radio(
        "¿Qué acción querés realizar?",
        ["Reposición de modelo existente", "Dar de alta un Nuevo Modelo", "✏️ Modificar o Eliminar un Modelo"],
        horizontal=True
    )
    
    # 1. REPOSICIÓN
    if tipo_accion == "Reposición de modelo existente":
        conn = get_connection()
        prod_rows = conn.execute("SELECT id_producto, nombre, stock_actual FROM productos WHERE id_producto != 'REFILL' ORDER BY nombre").fetchall()
        conn.close()
        
        opc_repo = {f"{p['id_producto']} - {p['nombre']} (Stock actual: {p['stock_actual']})": p for p in prod_rows}
        
        prod_repo_sel = st.selectbox(
            "Seleccioná el producto a reponer:",
            options=list(opc_repo.keys()),
            index=None,
            placeholder="Escribí o seleccioná un producto...",
            key=f"repo_prod_{st.session_state.reset_repo}"
        )
        
        cant_repo = st.number_input(
            "Cantidad ingresada:",
            min_value=1,
            value=1,
            step=1,
            key=f"repo_cant_{st.session_state.reset_repo}"
        )
        
        if st.button("Registrar Reposición 📦", type="primary"):
            if prod_repo_sel is None:
                st.warning("⚠️ Primero seleccioná un producto de la lista.")
            else:
                prod_obj = opc_repo[prod_repo_sel]
                conn = get_connection()
                cur = conn.cursor()
                
                cur.execute("""
                INSERT INTO movimientos_stock (id_producto, tipo_movimiento, cantidad)
                VALUES (?, 'Reposición de stock', ?)
                """, (prod_obj["id_producto"], cant_repo))
                
                cur.execute("""
                UPDATE productos SET stock_actual = stock_actual + ? WHERE id_producto = ?
                """, (cant_repo, prod_obj["id_producto"]))
                
                conn.commit()
                conn.close()
                
                st.session_state.reset_repo += 1
                st.success(f"¡Se sumaron {cant_repo} unidades a '{prod_obj['nombre']}'!")
                st.rerun()

    # 2. NUEVO MODELO
    elif tipo_accion == "Dar de alta un Nuevo Modelo":
        st.markdown("#### Datos del Nuevo Modelo")
        c1, c2 = st.columns(2)
        with c1:
            nuevo_id = st.text_input("Código único:", placeholder="Ej: 050, 15A3, ACC-02", key=f"n_id_{st.session_state.reset_nuevo}")
            nuevo_nombre = st.text_input("Nombre / Descripción:", placeholder="Ej: Vaso rayado XL", key=f"n_nom_{st.session_state.reset_nuevo}")
            nuevo_tipo = st.selectbox("Línea:", ["Recipiente", "Molde", "Accesorio"], key=f"n_tip_{st.session_state.reset_nuevo}")
        with c2:
            nuevo_cera = st.number_input("Gramos de cera (0 si es accesorio):", min_value=0.0, value=0.0, step=5.0, key=f"n_cer_{st.session_state.reset_nuevo}")
            nuevo_costo_env = st.number_input("Costo envase/molde o compra ($):", min_value=0.0, value=0.0, step=100.0, key=f"n_cos_{st.session_state.reset_nuevo}")
            nuevo_precio = st.number_input("Precio de venta al público ($):", min_value=0.0, value=0.0, step=500.0, key=f"n_pre_{st.session_state.reset_nuevo}")
            stock_inicial = st.number_input("Stock inicial elaborado:", min_value=0, value=0, step=1, key=f"n_stk_{st.session_state.reset_nuevo}")
            
        if st.button("Guardar Nuevo Producto ✨", type="primary"):
            if not nuevo_id.strip() or not nuevo_nombre.strip():
                st.error("⚠️ Por favor completá el código y el nombre.")
            elif nuevo_precio <= 0:
                st.error("⚠️ El precio de venta debe ser mayor a $0.")
            else:
                conn = get_connection()
                cur = conn.cursor()
                
                existe = cur.execute("SELECT 1 FROM productos WHERE id_producto = ?", (nuevo_id.strip(),)).fetchone()
                if existe:
                    st.error(f"El código '{nuevo_id}' ya existe en el catálogo.")
                    conn.close()
                else:
                    ins_dict = {row["nombre"]: row["costo_unitario"] for row in cur.execute("SELECT nombre, costo_unitario FROM insumos").fetchall()}
                    cera_apf = float(ins_dict.get("CERA APF", 15.0))
                    cera_bpf = float(ins_dict.get("CERA BPF", 8.0))
                    endurecedor = float(ins_dict.get("ENDURECEDOR", 25.0))
                    cera_bpf_end = float(ins_dict.get("BPF + END. 92/8", (cera_bpf * 0.92 + endurecedor * 0.08)))
                    
                    esencia = float(ins_dict.get("ESENCIAS", 350.0))
                    color = float(ins_dict.get("COLORANTE", 50.0))
                    pabilo = float(ins_dict.get("PABILO", 85.0))
                    cinta = float(ins_dict.get("CINTA / PEGAMENTO", 30.0))
                    ojalillo = float(ins_dict.get("OJALILLO", 30.0))
                    caja = float(ins_dict.get("CAJA GRANDE 11X11", 500.0))
                    
                    if nuevo_tipo == "Recipiente":
                        costo_calc = nuevo_costo_env + (nuevo_cera * cera_bpf_end) + esencia + pabilo + cinta + ojalillo + caja
                        sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                    elif nuevo_tipo == "Molde":
                        costo_calc = (nuevo_costo_env / 30.0) + (nuevo_cera * cera_apf) + esencia + color + pabilo + ojalillo
                        sugerido = math.ceil(costo_calc * 2.0 / 10.0) * 10
                    else:
                        costo_calc = nuevo_costo_env
                        sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                        
                    cur.execute("""
                    INSERT INTO productos (id_producto, nombre, tipo_linea, gramos_cera, costo_recipiente_o_molde, costo_fabricacion, precio_venta_sugerido, precio_venta_actual, stock_minimo_alerta, stock_actual)
                    VALUES (?, ?, ?, ?, ?, ROUND(?, 0), ?, ?, 1, ?)
                    """, (nuevo_id.strip(), nuevo_nombre.strip(), nuevo_tipo, nuevo_cera, nuevo_costo_env, costo_calc, sugerido, nuevo_precio, stock_inicial))
                    
                    if stock_inicial > 0:
                        cur.execute("""
                        INSERT INTO movimientos_stock (id_producto, tipo_movimiento, cantidad)
                        VALUES (?, 'Ingreso de nuevo modelo', ?)
                        """, (nuevo_id.strip(), stock_inicial))
                        
                    conn.commit()
                    conn.close()
                    
                    st.session_state.reset_nuevo += 1
                    st.success(f"¡Producto '{nuevo_nombre}' guardado exitosamente!")
                    st.rerun()

    # 3. MODIFICAR O ELIMINAR
    else:
        st.markdown("#### Modificar o Eliminar un Producto Existente")
        conn = get_connection()
        prod_rows = conn.execute("SELECT * FROM productos WHERE id_producto != 'REFILL' ORDER BY nombre").fetchall()
        conn.close()
        
        opc_mod = {f"{p['id_producto']} - {p['nombre']}": p for p in prod_rows}
        
        prod_mod_sel = st.selectbox(
            "Seleccioná el producto que querés editar o eliminar:",
            options=list(opc_mod.keys()),
            index=None,
            placeholder="Buscar por código o nombre...",
            key=f"mod_prod_{st.session_state.reset_mod}"
        )
        
        if prod_mod_sel is not None:
            p_actual = opc_mod[prod_mod_sel]
            
            st.info(f"Editando: **{p_actual['nombre']}** (Código: `{p_actual['id_producto']}`)")
            
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                edit_nombre = st.text_input("Nombre / Descripción:", value=p_actual["nombre"])
                lineas_disponibles = ["Recipiente", "Molde", "Accesorio"]
                idx_linea = lineas_disponibles.index(p_actual["tipo_linea"]) if p_actual["tipo_linea"] in lineas_disponibles else 0
                edit_tipo = st.selectbox("Línea:", lineas_disponibles, index=idx_linea)
                edit_cera = st.number_input("Gramos de cera:", min_value=0.0, value=float(p_actual["gramos_cera"] or 0), step=5.0)
            with m_col2:
                edit_costo_env = st.number_input("Costo de envase / molde / compra ($):", min_value=0.0, value=float(p_actual["costo_recipiente_o_molde"] or 0), step=100.0)
                edit_precio = st.number_input("Precio de venta al público ($):", min_value=0.0, value=float(p_actual["precio_venta_actual"] or 0), step=100.0)
                edit_stock = st.number_input("Stock actual en taller:", min_value=0, value=int(p_actual["stock_actual"] or 0), step=1)
                
            st.write("")
            b_guardar, _, b_borrar = st.columns([4, 2, 3])
            
            with b_guardar:
                if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                    conn = get_connection()
                    cur = conn.cursor()
                    
                    ins_dict = {row["nombre"]: row["costo_unitario"] for row in cur.execute("SELECT nombre, costo_unitario FROM insumos").fetchall()}
                    cera_apf = float(ins_dict.get("CERA APF", 15.0))
                    cera_bpf = float(ins_dict.get("CERA BPF", 8.0))
                    endurecedor = float(ins_dict.get("ENDURECEDOR", 25.0))
                    cera_bpf_end = float(ins_dict.get("BPF + END. 92/8", (cera_bpf * 0.92 + endurecedor * 0.08)))
                    
                    esencia = float(ins_dict.get("ESENCIAS", 350.0))
                    color = float(ins_dict.get("COLORANTE", 50.0))
                    pabilo = float(ins_dict.get("PABILO", 85.0))
                    cinta = float(ins_dict.get("CINTA / PEGAMENTO", 30.0))
                    ojalillo = float(ins_dict.get("OJALILLO", 30.0))
                    caja = float(ins_dict.get("CAJA GRANDE 11X11", 500.0))
                    
                    if edit_tipo == "Recipiente":
                        costo_calc = edit_costo_env + (edit_cera * cera_bpf_end) + esencia + pabilo + cinta + ojalillo + caja
                        sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                    elif edit_tipo == "Molde":
                        costo_calc = (edit_costo_env / 30.0) + (edit_cera * cera_apf) + esencia + color + pabilo + ojalillo
                        sugerido = math.ceil(costo_calc * 2.0 / 10.0) * 10
                    else:
                        costo_calc = edit_costo_env
                        sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                    
                    cur.execute("""
                    UPDATE productos 
                    SET nombre = ?, tipo_linea = ?, gramos_cera = ?, costo_recipiente_o_molde = ?,
                        costo_fabricacion = ROUND(?, 0), precio_venta_sugerido = ?,
                        precio_venta_actual = ?, stock_actual = ?
                    WHERE id_producto = ?
                    """, (edit_nombre.strip(), edit_tipo, edit_cera, edit_costo_env, costo_calc, sugerido, edit_precio, edit_stock, p_actual["id_producto"]))
                    conn.commit()
                    conn.close()
                    st.success(f"¡Datos y costos de '{edit_nombre}' actualizados correctamente!")
                    st.session_state.reset_mod += 1
                    st.rerun()
                    
            with b_borrar:
                if st.button("🗑️ Eliminar Producto", type="secondary", use_container_width=True):
                    conn = get_connection()
                    cur = conn.cursor()
                    
                    ventas_asociadas = cur.execute("SELECT COUNT(*) FROM ventas WHERE id_producto = ?", (p_actual["id_producto"],)).fetchone()[0]
                    
                    if ventas_asociadas > 0:
                        st.error(f"⚠️ No se puede eliminar '{p_actual['nombre']}' porque ya tiene {ventas_asociadas} venta(s) registrada(s).")
                        conn.close()
                    else:
                        cur.execute("DELETE FROM movimientos_stock WHERE id_producto = ?", (p_actual["id_producto"],))
                        cur.execute("DELETE FROM productos WHERE id_producto = ?", (p_actual["id_producto"],))
                        conn.commit()
                        conn.close()
                        st.session_state.reset_mod += 1
                        st.success(f"¡Producto '{p_actual['nombre']}' eliminado del catálogo con éxito!")
                        st.rerun()

# =========================================================
# TAB 3: REGISTRAR VENTA
# =========================================================
with tab_ventas:
    st.subheader("Registrar Venta Minorista")
    
    tipo_item_venta = st.radio("¿Qué querés agregar al pedido?", ["🕯️ Vela / Producto de Catálogo", "🔄 Refill (Relleno de Cera)"], horizontal=True)
    
    conn = get_connection()
    cur = conn.cursor()
    
    ins_dict = {row["nombre"]: row["costo_unitario"] for row in cur.execute("SELECT nombre, costo_unitario FROM insumos").fetchall()}
    
    cera_bpf = float(ins_dict.get("CERA BPF", 8.0))
    endurecedor = float(ins_dict.get("ENDURECEDOR", 25.0))
    cera_bpf_end = float(ins_dict.get("BPF + END. 92/8", (cera_bpf * 0.92 + endurecedor * 0.08)))
    
    esencia = float(ins_dict.get("ESENCIAS", 350.0))
    pabilo = float(ins_dict.get("PABILO", 85.0))
    cinta = float(ins_dict.get("CINTA / PEGAMENTO", 30.0))
    ojalillo = float(ins_dict.get("OJALILLO", 30.0))
    
    margen_refill_fijado = float(ins_dict.get("MULTIPLICADOR MARGEN REFILL", 3.0))
    
    # 1. VENTA DE PRODUCTO COMÚN
    if tipo_item_venta == "🕯️ Vela / Producto de Catálogo":
        prod_rows = cur.execute("SELECT id_producto, nombre, precio_venta_actual, stock_actual FROM productos WHERE id_producto != 'REFILL' ORDER BY nombre").fetchall()
        conn.close()
        
        opciones = {f"{p['id_producto']} - {p['nombre']} (Stock: {p['stock_actual']})": p for p in prod_rows}
        
        c_prod, c_cant, c_add = st.columns([5, 2, 2])
        with c_prod:
            seleccion = st.selectbox(
                "Elegí el producto:",
                options=list(opciones.keys()),
                index=None,
                placeholder="Buscar por código o nombre...",
                key=f"sel_item_{st.session_state.item_selector_key}"
            )
        with c_cant:
            cant_item = st.number_input("Cantidad:", min_value=1, value=1, step=1, key=f"cant_item_{st.session_state.item_selector_key}")
            
        with c_add:
            st.write("")
            st.write("")
            if st.button("➕ Agregar al pedido", use_container_width=True):
                if seleccion is None:
                    st.warning("Elegí un producto primero.")
                else:
                    p_elegido = opciones[seleccion]
                    subtotal = cant_item * p_elegido["precio_venta_actual"]
                    
                    ya_esta = False
                    for item in st.session_state.carrito:
                        if item["id_producto"] == p_elegido["id_producto"]:
                            item["cantidad"] += cant_item
                            item["subtotal"] = item["cantidad"] * item["precio_unitario"]
                            ya_esta = True
                            break
                    if not ya_esta:
                        st.session_state.carrito.append({
                            "id_producto": p_elegido["id_producto"],
                            "nombre": p_elegido["nombre"],
                            "precio_unitario": p_elegido["precio_venta_actual"],
                            "cantidad": cant_item,
                            "subtotal": subtotal,
                            "stock_disponible": p_elegido["stock_actual"],
                            "es_refill": False
                        })
                    st.session_state.item_selector_key += 1
                    st.rerun()

    # 2. VENTA DE REFILL DINÁMICO
    else:
        conn.close()
        st.markdown(f"##### Carga de Refill (Costo mezcla: **${cera_bpf_end:.2f} / g** | Margen automático: **{margen_refill_fijado}x**)")
        
        c_rf_gr, c_rf_desc = st.columns([4, 6])
        with c_rf_gr:
            gramos_refill = st.number_input("Gramos de cera a recargar:", min_value=10.0, value=150.0, step=5.0, key=f"gr_rf_{st.session_state.item_selector_key}")
        with c_rf_desc:
            desc_frasco = st.text_input("Detalle del envase / cliente (opcional):", placeholder="Ej: Vaso whisky propio, frasco mermelada...", key=f"desc_rf_{st.session_state.item_selector_key}")
            
        costo_cera = gramos_refill * cera_bpf_end
        costo_fijo_armado = esencia + pabilo + cinta + ojalillo
        costo_total_refill = costo_cera + costo_fijo_armado
        
        precio_refill_sugerido = math.ceil((costo_total_refill * margen_refill_fijado) / 10.0) * 10
        
        c_p1, c_p2, c_p3 = st.columns([4, 4, 3])
        with c_p1:
            st.caption(f"Cera ({gramos_refill:,.0f}g × ${cera_bpf_end:.2f}): **${costo_cera:,.1f}** | Armado: **${costo_fijo_armado:,.0f}**")
            st.info(f"Costo elaboración: **${costo_total_refill:,.0f}** | Sugerido: **${precio_refill_sugerido:,.0f}**")
        with c_p2:
            precio_final_refill = st.number_input("Precio a cobrar ($):", min_value=0.0, value=float(precio_refill_sugerido), step=100.0)
        with c_p3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar Refill al pedido", use_container_width=True):
                nombre_detalle = f"Refill de cera ({gramos_refill:,.0f}g)"
                if desc_frasco.strip():
                    nombre_detalle += f" - {desc_frasco.strip()}"
                    
                st.session_state.carrito.append({
                    "id_producto": "REFILL",
                    "nombre": nombre_detalle,
                    "precio_unitario": precio_final_refill,
                    "cantidad": 1,
                    "subtotal": precio_final_refill,
                    "stock_disponible": 9999,
                    "es_refill": True
                })
                st.session_state.item_selector_key += 1
                st.rerun()

    # DETALLE DEL PEDIDO (CARRITO)
    st.write("---")
    st.markdown("##### 📋 Detalle de la venta en curso")
    
    if len(st.session_state.carrito) == 0:
        st.info("🛒 El pedido está vacío. Agregá productos o refills arriba.")
    else:
        filas_tabla = []
        total_venta = 0
        hay_alerta_stock = False
        
        for idx, item in enumerate(st.session_state.carrito):
            total_venta += item["subtotal"]
            aviso = ""
            if not item.get("es_refill", False) and item["stock_disponible"] < item["cantidad"]:
                aviso = f"⚠️ (Stock disp: {item['stock_disponible']})"
                hay_alerta_stock = True
                
            filas_tabla.append({
                "N°": idx + 1,
                "Código": item["id_producto"],
                "Detalle del Producto": f"{item['nombre']} {aviso}",
                "Cant.": item["cantidad"],
                "Precio Unit. ($)": f"${item['precio_unitario']:,.0f}",
                "Subtotal ($)": f"${item['subtotal']:,.0f}"
            })
            
        st.dataframe(pd.DataFrame(filas_tabla), use_container_width=True, hide_index=True)
        
        c_tot1, c_tot2 = st.columns([6, 3])
        with c_tot2:
            st.markdown(f"### Total a Cobrar: :green[**${total_venta:,.0f}**]")
            
        if hay_alerta_stock:
            st.warning("⚠️ Uno o más productos de catálogo superan el stock registrado en sistema.")
            
        c_cli, c_btn_cancel, c_btn_conf = st.columns([4, 2, 3])
        with c_cli:
            cliente_venta = st.text_input("Nombre del cliente (opcional):", placeholder="Ej: Sofía Gómez")
        with c_btn_cancel:
            st.write("")
            st.write("")
            if st.button("🗑️ Vaciar pedido", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()
        with c_btn_conf:
            st.write("")
            st.write("")
            if st.button("Confirmar Venta Completa 🛒", type="primary", use_container_width=True):
                conn = get_connection()
                cur = conn.cursor()
                
                cur.execute("SELECT IFNULL(MAX(nro_ticket), 0) + 1 FROM ventas")
                nuevo_ticket = cur.fetchone()[0]
                
                for item in st.session_state.carrito:
                    cur.execute("""
                    INSERT INTO ventas (nro_ticket, id_producto, cantidad, precio_unitario, total_venta, cliente)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (nuevo_ticket, item["id_producto"], item["cantidad"], item["precio_unitario"], item["subtotal"], cliente_venta.strip() if cliente_venta else None))
                    
                    if not item.get("es_refill", False):
                        cur.execute("""
                        UPDATE productos SET stock_actual = stock_actual - ? WHERE id_producto = ?
                        """, (item["cantidad"], item["id_producto"]))
                    
                conn.commit()
                conn.close()
                
                st.session_state.carrito = []
                st.session_state.item_selector_key += 1
                st.success(f"¡Venta registrada con éxito bajo el Ticket N° {nuevo_ticket}!")
                st.rerun()

# =========================================================
# TAB 4: HISTORIAL DE VENTAS
# =========================================================
with tab_historial:
    st.subheader("Registro Histórico de Ventas")
    conn = get_connection()
    df_v = pd.read_sql_query("""
    SELECT IFNULL(v.nro_ticket, v.id_venta) AS [N° Ticket], v.fecha AS Fecha,
           IFNULL(v.cliente, '-') AS Cliente, 
           CASE WHEN v.id_producto = 'REFILL' THEN 'Servicio de Refill' ELSE p.nombre END AS Producto,
           v.cantidad AS Cantidad, v.precio_unitario AS [Precio Unitario],
           v.total_venta AS [Subtotal ($)]
    FROM ventas v
    LEFT JOIN productos p ON v.id_producto = p.id_producto
    ORDER BY v.id_venta DESC
    """, conn)
    conn.close()
    
    if df_v.empty:
        st.info("Todavía no se registraron ventas.")
    else:
        df_v["Precio Unitario"] = df_v["Precio Unitario"].apply(lambda x: f"${x:,.0f}")
        df_v["Subtotal ($)"] = df_v["Subtotal ($)"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df_v, use_container_width=True, hide_index=True)

# =========================================================
# TAB 5: GESTIÓN DE INSUMOS, COSTOS Y MÁRGENES
# =========================================================
with tab_config:
    st.subheader("⚙️ Gestión de Insumos y Precios de Venta")
    
    subtab_insumos, tab_recalculo, subtab_tablas = st.tabs([
        "💰 Precios de Insumos",
        "📈 Recalcular Costos y Precios",
        "🗄️ Explorador de Tablas"
    ])
    
    # 1. ACTUALIZAR INSUMOS
    with subtab_insumos:
        st.markdown("##### Precios actuales de materias primas e insumos")
        conn = get_connection()
        df_ins = pd.read_sql_query("""
        SELECT id_insumo, nombre, categoria, unidad_medida, costo_unitario 
        FROM insumos 
        WHERE id_insumo NOT LIKE 'CFG-%' AND id_insumo != 'INS-REF'
        ORDER BY id_insumo
        """, conn)
        conn.close()
        
        st.caption("Podés editar los valores con centavos. La fila 'BPF + END. 92/8' se calcula sola en base a Cera BPF y Endurecedor.")
        
        df_ins_edit = st.data_editor(
            df_ins,
            column_config={
                "id_insumo": st.column_config.TextColumn("Código", disabled=True),
                "nombre": st.column_config.TextColumn("Insumo / Concepto", disabled=True),
                "categoria": st.column_config.TextColumn("Categoría", disabled=True),
                "unidad_medida": st.column_config.TextColumn("Unidad", disabled=True),
                "costo_unitario": st.column_config.NumberColumn("Costo ($)", min_value=0.0, step=0.01, format="$%.2f")
            },
            hide_index=True,
            use_container_width=True,
            key="editor_insumos"
        )
        
        if st.button("💾 Guardar Precios de Insumos", type="primary"):
            conn = get_connection()
            cur = conn.cursor()
            
            for _, row in df_ins_edit.iterrows():
                cur.execute("UPDATE insumos SET costo_unitario = ? WHERE id_insumo = ?", (float(row["costo_unitario"]), row["id_insumo"]))
                
            cur.execute("""
            UPDATE insumos 
            SET costo_unitario = ROUND((
                (SELECT costo_unitario FROM insumos WHERE id_insumo = 'INS-02') * 0.92 +
                (SELECT costo_unitario FROM insumos WHERE id_insumo = 'INS-03') * 0.08
            ), 2)
            WHERE id_insumo = 'INS-04'
            """)
            
            conn.commit()
            conn.close()
            st.success("¡Precios de insumos guardados y mezcla recalculada automáticamente!")
            st.rerun()

    # 2. RECALCULAR COSTOS Y MÁRGENES
    with tab_recalculo:
        st.markdown("##### Actualizar Costos de Fabricación y Precios de Venta")
        st.info("Configurá los multiplicadores de margen para cada línea y recalculá los costos y precios sugeridos.")
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT costo_unitario FROM insumos WHERE id_insumo = 'CFG-MARGEN-REF'")
        row_mg_ref = cur.fetchone()
        val_margen_ref = float(row_mg_ref[0]) if row_mg_ref else 3.0
        conn.close()
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            margen_recipiente = st.number_input("Multiplicador para Recipientes:", min_value=1.0, value=1.5, step=0.1)
        with col_m2:
            margen_molde = st.number_input("Multiplicador para Moldes:", min_value=1.0, value=2.0, step=0.1)
        with col_m3:
            margen_refill_cfg = st.number_input("Multiplicador para Refill:", min_value=1.0, value=val_margen_ref, step=0.1)
            
        if st.button("🔄 Recalcular Costos y Precios Sugeridos", type="secondary"):
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("UPDATE insumos SET costo_unitario = ? WHERE id_insumo = 'CFG-MARGEN-REF'", (margen_refill_cfg,))
            
            ins_dict = {row["nombre"]: row["costo_unitario"] for row in cur.execute("SELECT nombre, costo_unitario FROM insumos").fetchall()}
            
            cera_apf = float(ins_dict.get("CERA APF", 15.0))
            cera_bpf = float(ins_dict.get("CERA BPF", 8.0))
            endurecedor = float(ins_dict.get("ENDURECEDOR", 25.0))
            cera_bpf_end = float(ins_dict.get("BPF + END. 92/8", (cera_bpf * 0.92 + endurecedor * 0.08)))
            
            esencia = float(ins_dict.get("ESENCIAS", 350.0))
            color = float(ins_dict.get("COLORANTE", 50.0))
            pabilo = float(ins_dict.get("PABILO", 85.0))
            cinta = float(ins_dict.get("CINTA / PEGAMENTO", 30.0))
            ojalillo = float(ins_dict.get("OJALILLO", 30.0))
            caja = float(ins_dict.get("CAJA GRANDE 11X11", 500.0))
            
            prods = cur.execute("SELECT id_producto, tipo_linea, gramos_cera, costo_recipiente_o_molde FROM productos WHERE id_producto != 'REFILL'").fetchall()
            for p in prods:
                pid, tipo, cera, env = p["id_producto"], p["tipo_linea"], p["gramos_cera"] or 0, p["costo_recipiente_o_molde"] or 0
                
                if tipo == "Recipiente":
                    costo_calc = env + (cera * cera_bpf_end) + esencia + pabilo + cinta + ojalillo + caja
                    sugerido = math.ceil(costo_calc * margen_recipiente / 10.0) * 10
                elif tipo == "Molde":
                    costo_calc = (env / 30.0) + (cera * cera_apf) + esencia + color + pabilo + ojalillo
                    sugerido = math.ceil(costo_calc * margen_molde / 10.0) * 10
                else:
                    costo_calc = env
                    sugerido = math.ceil(costo_calc * margen_recipiente / 10.0) * 10
                    
                cur.execute("""
                UPDATE productos 
                SET costo_fabricacion = ROUND(?, 0), precio_venta_sugerido = ?
                WHERE id_producto = ?
                """, (costo_calc, sugerido, pid))
                
            conn.commit()
            conn.close()
            st.success("¡Costos, precios sugeridos y margen de refill actualizados correctamente!")
            st.rerun()
            
        st.write("---")
        st.markdown("##### Ajuste manual de Precios de Venta Actuales")
        conn = get_connection()
        df_ajuste = pd.read_sql_query("""
        SELECT id_producto, nombre, tipo_linea, costo_fabricacion, precio_venta_sugerido, precio_venta_actual
        FROM productos WHERE id_producto != 'REFILL' ORDER BY tipo_linea, nombre
        """, conn)
        conn.close()
        
        def estado_comparacion(row):
            sug = row["precio_venta_sugerido"] or 0
            vta = row["precio_venta_actual"] or 0
            if sug > 0 and vta < sug:
                return f"⚠️ Por debajo (-${sug - vta:,.0f})"
            elif sug > 0:
                return "✅ OK"
            else:
                return "⚪ Sin sugerido"
                
        df_ajuste["Estado / Alerta"] = df_ajuste.apply(estado_comparacion, axis=1)
        
        df_ajuste_edit = st.data_editor(
            df_ajuste,
            column_config={
                "id_producto": st.column_config.TextColumn("Código", disabled=True),
                "nombre": st.column_config.TextColumn("Producto", disabled=True),
                "tipo_linea": st.column_config.TextColumn("Línea", disabled=True),
                "costo_fabricacion": st.column_config.NumberColumn("Costo Fab. ($)", format="$%.0f", disabled=True),
                "precio_venta_sugerido": st.column_config.NumberColumn("Precio Sugerido ($)", format="$%.0f", disabled=True),
                "precio_venta_actual": st.column_config.NumberColumn("Precio Venta Actual ($)", min_value=0.0, step=100.0, format="$%.0f"),
                "Estado / Alerta": st.column_config.TextColumn("Estado / Alerta", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_precios"
        )
        
        if st.button("💾 Guardar Precios de Venta Actualizados", type="primary"):
            conn = get_connection()
            cur = conn.cursor()
            for _, r in df_ajuste_edit.iterrows():
                cur.execute("UPDATE productos SET precio_venta_actual = ? WHERE id_producto = ?", (r["precio_venta_actual"], r["id_producto"]))
            conn.commit()
            conn.close()
            st.success("¡Precios de venta al público actualizados con éxito!")
            st.rerun()

    # 3. EXPLORADOR DE TABLAS
    with subtab_tablas:
        st.markdown("##### Visualizador de Tablas de la Base de Datos")
        tabla_sel = st.selectbox("Seleccioná la tabla que querés inspeccionar:", ["productos", "ventas", "movimientos_stock", "insumos"])
        
        conn = get_connection()
        df_raw = pd.read_sql_query(f"SELECT * FROM {tabla_sel}", conn)
        conn.close()
        
        st.dataframe(df_raw, use_container_width=True)
        st.caption(f"Mostrando {len(df_raw)} registros de la tabla '{tabla_sel}'.")