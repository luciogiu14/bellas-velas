import streamlit as st
import pandas as pd
import math
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

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
CLAVE_CORRECTA = "bellasvelas"

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

if not check_password():
    st.stop()

with st.sidebar:
    st.caption("Sesión activa")
    if st.button("Cerrar Sesión 🚪", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# =========================================================
# CONEXIÓN CON GOOGLE SHEETS
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)

def leer_hoja(worksheet_name):
    # ttl=0 asegura leer siempre los datos más frescos sin caché obsoleta
    df = conn.read(worksheet=worksheet_name, ttl=0)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.dropna(how="all")

def escribir_hoja(worksheet_name, df):
    conn.update(worksheet=worksheet_name, data=df)

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

st.title("🕯️ Bellas Velas - Control de Stock y Ventas")

# Carga de tablas base
df_productos = leer_hoja("productos")
df_insumos = leer_hoja("insumos")

# Asegurar tipos numéricos en productos
cols_num_prod = ["gramos_cera", "costo_recipiente_o_molde", "costo_fabricacion", "precio_venta_sugerido", "precio_venta_actual", "stock_minimo_alerta", "stock_actual"]
for c in cols_num_prod:
    if c in df_productos.columns:
        df_productos[c] = pd.to_numeric(df_productos[c], errors="coerce").fillna(0)

# Asegurar tipos numéricos en insumos
if not df_insumos.empty and "costo_unitario" in df_insumos.columns:
    df_insumos["costo_unitario"] = pd.to_numeric(df_insumos["costo_unitario"], errors="coerce").fillna(0.0)

# Diccionario rápido de insumos
dict_insumos = {}
if not df_insumos.empty:
    for _, row in df_insumos.iterrows():
        dict_insumos[str(row["nombre"]).strip()] = float(row["costo_unitario"])

cera_bpf = dict_insumos.get("CERA BPF", 8.0)
endurecedor = dict_insumos.get("ENDURECEDOR", 25.0)
cera_bpf_end = dict_insumos.get("BPF + END. 92/8", (cera_bpf * 0.92 + endurecedor * 0.08))
cera_apf = dict_insumos.get("CERA APF", 15.0)
esencia = dict_insumos.get("ESENCIAS", 350.0)
color = dict_insumos.get("COLORANTE", 50.0)
pabilo = dict_insumos.get("PABILO", 85.0)
cinta = dict_insumos.get("CINTA / PEGAMENTO", 30.0)
ojalillo = dict_insumos.get("OJALILLO", 30.0)
caja_grande = dict_insumos.get("CAJA GRANDE 11X11", 500.0)
margen_refill_fijado = dict_insumos.get("MULTIPLICADOR MARGEN REFILL", 3.0)

# Pestañas principales
tab_consulta, tab_stock, tab_ventas, tab_historial, tab_config = st.tabs([
    "🔍 Consultar Precios y Stock",
    "📦 Ingreso de Stock / Catálogo",
    "🛒 Registrar Venta",
    "📊 Historial de Ventas",
    "⚙️ Insumos y Precios"
])

# =========================================================
# TAB 1: CONSULTA RÁPIDA
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
        
    df_mostrar = df_productos[df_productos["id_producto"] != "REFILL"].copy()
    
    if busqueda and busqueda.strip():
        termino = busqueda.strip().lower()
        df_mostrar = df_mostrar[
            df_mostrar["id_producto"].astype(str).str.lower().str.contains(termino, na=False) |
            df_mostrar["nombre"].astype(str).str.lower().str.contains(termino, na=False)
        ]
        
    if filtro_linea != "Todas":
        df_mostrar = df_mostrar[df_mostrar["tipo_linea"] == filtro_linea]
        
    if df_mostrar.empty:
        st.info("No se encontraron productos con ese criterio de búsqueda.")
    else:
        def alerta_precio(row):
            sugerido = row["precio_venta_sugerido"] or 0
            venta = row["precio_venta_actual"] or 0
            if sugerido > 0 and venta < sugerido:
                return f"⚠️ Menor al sugerido (-${sugerido - venta:,.0f})"
            elif sugerido > 0:
                return "✅ Óptimo"
            else:
                return "⚪ Sin calcular"
                
        def semaforo_stock(row):
            stock = row["stock_actual"]
            minimo = row["stock_minimo_alerta"]
            if stock <= 0:
                return "🔴 Sin Stock"
            elif stock <= minimo:
                return "🟡 Stock Bajo"
            else:
                return "🟢 Disponible"
                
        df_mostrar["Alerta Precio"] = df_mostrar.apply(alerta_precio, axis=1)
        df_mostrar["Estado Stock"] = df_mostrar.apply(semaforo_stock, axis=1)
        
        df_formateada = pd.DataFrame()
        df_formateada["Código"] = df_mostrar["id_producto"]
        df_formateada["Descripción"] = df_mostrar["nombre"]
        df_formateada["Línea"] = df_mostrar["tipo_linea"]
        df_formateada["Grs Cera"] = df_mostrar["gramos_cera"].apply(lambda x: f"{x:,.0f} g" if x > 0 else "-")
        df_formateada["Costo Envase ($)"] = df_mostrar["costo_recipiente_o_molde"].apply(lambda x: f"${x:,.0f}")
        df_formateada["Costo Fab. ($)"] = df_mostrar["costo_fabricacion"].apply(lambda x: f"${x:,.0f}")
        df_formateada["Precio Sugerido ($)"] = df_mostrar["precio_venta_sugerido"].apply(lambda x: f"${x:,.0f}")
        df_formateada["Precio Venta ($)"] = df_mostrar["precio_venta_actual"].apply(lambda x: f"${x:,.0f}")
        df_formateada["Alerta Precio"] = df_mostrar["Alerta Precio"]
        df_formateada["Stock Disp."] = df_mostrar["stock_actual"].astype(int)
        df_formateada["Estado Stock"] = df_mostrar["Estado Stock"]
        
        st.dataframe(df_formateada, use_container_width=True, hide_index=True)

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
        prod_catalogo = df_productos[df_productos["id_producto"] != "REFILL"].sort_values("nombre")
        opc_repo = {f"{r['id_producto']} - {r['nombre']} (Stock actual: {int(r['stock_actual'])})": r for _, r in prod_catalogo.iterrows()}
        
        prod_repo_sel = st.selectbox(
            "Seleccioná el producto a reponer:",
            options=list(opc_repo.keys()),
            index=None,
            placeholder="Escribí o seleccioná un producto...",
            key=f"repo_prod_{st.session_state.reset_repo}"
        )
        
        cant_repo = st.number_input("Cantidad ingresada:", min_value=1, value=1, step=1, key=f"repo_cant_{st.session_state.reset_repo}")
        
        if st.button("Registrar Reposición 📦", type="primary"):
            if prod_repo_sel is None:
                st.warning("⚠️ Primero seleccioná un producto de la lista.")
            else:
                prod_obj = opc_repo[prod_repo_sel]
                pid = prod_obj["id_producto"]
                
                # Actualizar stock en productos
                df_productos.loc[df_productos["id_producto"] == pid, "stock_actual"] += cant_repo
                escribir_hoja("productos", df_productos)
                
                # Registrar en movimientos_stock
                df_mov = leer_hoja("movimientos_stock")
                nuevo_id_mov = 1 if df_mov.empty or "id_movimiento" not in df_mov.columns else int(pd.to_numeric(df_mov["id_movimiento"], errors="coerce").max() or 0) + 1
                nueva_fila_mov = pd.DataFrame([{
                    "id_movimiento": nuevo_id_mov,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "id_producto": pid,
                    "tipo_movimiento": "Reposición de stock",
                    "cantidad": cant_repo
                }])
                df_mov = pd.concat([df_mov, nueva_fila_mov], ignore_index=True)
                escribir_hoja("movimientos_stock", df_mov)
                
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
            elif (df_productos["id_producto"].astype(str) == nuevo_id.strip()).any():
                st.error(f"El código '{nuevo_id}' ya existe en el catálogo.")
            else:
                if nuevo_tipo == "Recipiente":
                    costo_calc = nuevo_costo_env + (nuevo_cera * cera_bpf_end) + esencia + pabilo + cinta + ojalillo + caja_grande
                    sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                elif nuevo_tipo == "Molde":
                    costo_calc = (nuevo_costo_env / 30.0) + (nuevo_cera * cera_apf) + esencia + color + pabilo + ojalillo
                    sugerido = math.ceil(costo_calc * 2.0 / 10.0) * 10
                else:
                    costo_calc = nuevo_costo_env
                    sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                    
                nueva_fila_prod = pd.DataFrame([{
                    "id_producto": nuevo_id.strip(),
                    "nombre": nuevo_nombre.strip(),
                    "tipo_linea": nuevo_tipo,
                    "gramos_cera": nuevo_cera,
                    "costo_recipiente_o_molde": nuevo_costo_env,
                    "costo_fabricacion": round(costo_calc, 0),
                    "precio_venta_sugerido": sugerido,
                    "precio_venta_actual": nuevo_precio,
                    "stock_minimo_alerta": 1,
                    "stock_actual": stock_inicial
                }])
                df_productos = pd.concat([df_productos, nueva_fila_prod], ignore_index=True)
                escribir_hoja("productos", df_productos)
                
                if stock_inicial > 0:
                    df_mov = leer_hoja("movimientos_stock")
                    nuevo_id_mov = 1 if df_mov.empty or "id_movimiento" not in df_mov.columns else int(pd.to_numeric(df_mov["id_movimiento"], errors="coerce").max() or 0) + 1
                    nueva_fila_mov = pd.DataFrame([{
                        "id_movimiento": nuevo_id_mov,
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "id_producto": nuevo_id.strip(),
                        "tipo_movimiento": "Ingreso de nuevo modelo",
                        "cantidad": stock_inicial
                    }])
                    df_mov = pd.concat([df_mov, nueva_fila_mov], ignore_index=True)
                    escribir_hoja("movimientos_stock", df_mov)
                    
                st.session_state.reset_nuevo += 1
                st.success(f"¡Producto '{nuevo_nombre}' guardado exitosamente!")
                st.rerun()

    # 3. MODIFICAR O ELIMINAR
    else:
        st.markdown("#### Modificar o Eliminar un Producto Existente")
        prod_catalogo = df_productos[df_productos["id_producto"] != "REFILL"].sort_values("nombre")
        opc_mod = {f"{r['id_producto']} - {r['nombre']}": r for _, r in prod_catalogo.iterrows()}
        
        prod_mod_sel = st.selectbox(
            "Seleccioná el producto que querés editar o eliminar:",
            options=list(opc_mod.keys()),
            index=None,
            placeholder="Buscar por código o nombre...",
            key=f"mod_prod_{st.session_state.reset_mod}"
        )
        
        if prod_mod_sel is not None:
            p_actual = opc_mod[prod_mod_sel]
            pid = p_actual["id_producto"]
            
            st.info(f"Editando: **{p_actual['nombre']}** (Código: `{pid}`)")
            
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                edit_nombre = st.text_input("Nombre / Descripción:", value=str(p_actual["nombre"]))
                lineas = ["Recipiente", "Molde", "Accesorio"]
                idx_linea = lineas.index(p_actual["tipo_linea"]) if p_actual["tipo_linea"] in lineas else 0
                edit_tipo = st.selectbox("Línea:", lineas, index=idx_linea)
                edit_cera = st.number_input("Gramos de cera:", min_value=0.0, value=float(p_actual["gramos_cera"] or 0), step=5.0)
            with m_col2:
                edit_costo_env = st.number_input("Costo de envase / molde / compra ($):", min_value=0.0, value=float(p_actual["costo_recipiente_o_molde"] or 0), step=100.0)
                edit_precio = st.number_input("Precio de venta al público ($):", min_value=0.0, value=float(p_actual["precio_venta_actual"] or 0), step=100.0)
                edit_stock = st.number_input("Stock actual en taller:", min_value=0, value=int(p_actual["stock_actual"] or 0), step=1)
                
            b_guardar, _, b_borrar = st.columns([4, 2, 3])
            
            with b_guardar:
                if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                    if edit_tipo == "Recipiente":
                        costo_calc = edit_costo_env + (edit_cera * cera_bpf_end) + esencia + pabilo + cinta + ojalillo + caja_grande
                        sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                    elif edit_tipo == "Molde":
                        costo_calc = (edit_costo_env / 30.0) + (edit_cera * cera_apf) + esencia + color + pabilo + ojalillo
                        sugerido = math.ceil(costo_calc * 2.0 / 10.0) * 10
                    else:
                        costo_calc = edit_costo_env
                        sugerido = math.ceil(costo_calc * 1.5 / 10.0) * 10
                        
                    idx_prod = df_productos[df_productos["id_producto"] == pid].index[0]
                    df_productos.at[idx_prod, "nombre"] = edit_nombre.strip()
                    df_productos.at[idx_prod, "tipo_linea"] = edit_tipo
                    df_productos.at[idx_prod, "gramos_cera"] = edit_cera
                    df_productos.at[idx_prod, "costo_recipiente_o_molde"] = edit_costo_env
                    df_productos.at[idx_prod, "costo_fabricacion"] = round(costo_calc, 0)
                    df_productos.at[idx_prod, "precio_venta_sugerido"] = sugerido
                    df_productos.at[idx_prod, "precio_venta_actual"] = edit_precio
                    df_productos.at[idx_prod, "stock_actual"] = edit_stock
                    
                    escribir_hoja("productos", df_productos)
                    st.session_state.reset_mod += 1
                    st.success(f"¡Datos de '{edit_nombre}' actualizados correctamente en Google Sheets!")
                    st.rerun()
                    
            with b_borrar:
                if st.button("🗑️ Eliminar Producto", type="secondary", use_container_width=True):
                    df_v = leer_hoja("ventas")
                    ventas_asoc = 0 if df_v.empty or "id_producto" not in df_v.columns else (df_v["id_producto"].astype(str) == str(pid)).sum()
                    
                    if ventas_asoc > 0:
                        st.error(f"⚠️ No se puede eliminar '{p_actual['nombre']}' porque tiene {ventas_asoc} venta(s) asociada(s).")
                    else:
                        df_productos = df_productos[df_productos["id_producto"] != pid]
                        escribir_hoja("productos", df_productos)
                        
                        df_mov = leer_hoja("movimientos_stock")
                        if not df_mov.empty and "id_producto" in df_mov.columns:
                            df_mov = df_mov[df_mov["id_producto"] != pid]
                            escribir_hoja("movimientos_stock", df_mov)
                            
                        st.session_state.reset_mod += 1
                        st.success(f"¡Producto '{p_actual['nombre']}' eliminado del catálogo!")
                        st.rerun()

# =========================================================
# TAB 3: REGISTRAR VENTA
# =========================================================
with tab_ventas:
    st.subheader("Registrar Venta Minorista")
    tipo_item_venta = st.radio("¿Qué querés agregar al pedido?", ["🕯️ Vela / Producto de Catálogo", "🔄 Refill (Relleno de Cera)"], horizontal=True)
    
    # 1. PRODUCTO DE CATÁLOGO
    if tipo_item_venta == "🕯️ Vela / Producto de Catálogo":
        prod_catalogo = df_productos[df_productos["id_producto"] != "REFILL"].sort_values("nombre")
        opciones = {f"{r['id_producto']} - {r['nombre']} (Stock: {int(r['stock_actual'])})": r for _, r in prod_catalogo.iterrows()}
        
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

    # 2. REFILL DINÁMICO
    else:
        st.markdown(f"##### Carga de Refill (Costo mezcla: **${cera_bpf_end:.2f} / g** | Margen: **{margen_refill_fijado}x**)")
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
            st.caption(f"Cera ({gramos_refill:,.0f}g × ${cera_bpf_end:.2f}): **${costo_cera:,.1f}** \vert{} Armado: **${costo_fijo_armado:,.0f}**")
            st.info(f"Costo elaboración: **${costo_total_refill:,.0f}** \vert{} Sugerido: **${precio_refill_sugerido:,.0f}**")
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
                aviso = f"⚠️ (Stock disp: {int(item['stock_disponible'])})"
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
                df_ventas = leer_hoja("ventas")
                
                ultimo_ticket = 0 if df_ventas.empty or "nro_ticket" not in df_ventas.columns else int(pd.to_numeric(df_ventas["nro_ticket"], errors="coerce").max() or 0)
                nuevo_ticket = ultimo_ticket + 1
                
                ultimo_id_venta = 0 if df_ventas.empty or "id_venta" not in df_ventas.columns else int(pd.to_numeric(df_ventas["id_venta"], errors="coerce").max() or 0)
                
                nuevas_ventas = []
                ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                for item in st.session_state.carrito:
                    ultimo_id_venta += 1
                    nuevas_ventas.append({
                        "id_venta": ultimo_id_venta,
                        "nro_ticket": nuevo_ticket,
                        "fecha": ahora_str,
                        "cliente": cliente_venta.strip() if cliente_venta else "-",
                        "id_producto": item["id_producto"],
                        "cantidad": item["cantidad"],
                        "precio_unitario": item["precio_unitario"],
                        "total_venta": item["subtotal"]
                    })
                    
                    if not item.get("es_refill", False):
                        df_productos.loc[df_productos["id_producto"] == item["id_producto"], "stock_actual"] -= item["cantidad"]
                
                df_ventas = pd.concat([df_ventas, pd.DataFrame(nuevas_ventas)], ignore_index=True)
                escribir_hoja("ventas", df_ventas)
                escribir_hoja("productos", df_productos)
                
                st.session_state.carrito = []
                st.session_state.item_selector_key += 1
                st.success(f"¡Venta registrada con éxito bajo el Ticket N° {nuevo_ticket} en Google Sheets!")
                st.rerun()

# =========================================================
# TAB 4: HISTORIAL DE VENTAS
# =========================================================
with tab_historial:
    st.subheader("Registro Histórico de Ventas")
    df_ventas = leer_hoja("ventas")
    
    if df_ventas.empty:
        st.info("Todavía no se registraron ventas en la planilla.")
    else:
        df_v_display = df_ventas.copy()
        
        # Unir con nombres de productos
        prod_map = dict(zip(df_productos["id_producto"].astype(str), df_productos["nombre"]))
        prod_map["REFILL"] = "Servicio de Refill"
        
        df_v_display["Producto"] = df_v_display["id_producto"].astype(str).map(prod_map).fillna(df_v_display["id_producto"])
        
        df_v_display = df_v_display.sort_values(by="id_venta", ascending=False)
        
        columnas_finales = pd.DataFrame()
        columnas_finales["N° Ticket"] = df_v_display["nro_ticket"]
        columnas_finales["Fecha"] = df_v_display["fecha"]
        columnas_finales["Cliente"] = df_v_display["cliente"]
        columnas_finales["Producto"] = df_v_display["Producto"]
        columnas_finales["Cantidad"] = df_v_display["cantidad"].astype(int)
        columnas_finales["Precio Unitario"] = pd.to_numeric(df_v_display["precio_unitario"], errors="coerce").apply(lambda x: f"${x:,.0f}")
        columnas_finales["Subtotal ($)"] = pd.to_numeric(df_v_display["total_venta"], errors="coerce").apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(columnas_finales, use_container_width=True, hide_index=True)

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
        df_ins_view = df_insumos[~df_insumos["id_insumo"].astype(str).str.startswith("CFG-") & (df_insumos["id_insumo"] != "INS-REF")].copy()
        
        st.caption("Podés editar los valores con centavos. Al guardar, la mezcla 92/8 se recalcula automáticamente.")
        
        df_ins_edit = st.data_editor(
            df_ins_view,
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
            for _, r in df_ins_edit.iterrows():
                df_insumos.loc[df_insumos["id_insumo"] == r["id_insumo"], "costo_unitario"] = float(r["costo_unitario"])
                
            val_bpf = float(df_insumos.loc[df_insumos["id_insumo"] == "INS-02", "costo_unitario"].values[0] if (df_insumos["id_insumo"] == "INS-02").any() else 8.0)
            val_end = float(df_insumos.loc[df_insumos["id_insumo"] == "INS-03", "costo_unitario"].values[0] if (df_insumos["id_insumo"] == "INS-03").any() else 25.0)
            nueva_mezcla = round((val_bpf * 0.92) + (val_end * 0.08), 2)
            
            if (df_insumos["id_insumo"] == "INS-04").any():
                df_insumos.loc[df_insumos["id_insumo"] == "INS-04", "costo_unitario"] = nueva_mezcla
                
            escribir_hoja("insumos", df_insumos)
            st.success("¡Precios de insumos y mezcla recalculados en Google Sheets!")
            st.rerun()

    # 2. RECALCULAR COSTOS Y MÁRGENES
    with tab_recalculo:
        st.markdown("##### Actualizar Costos de Fabricación y Precios de Venta")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            margen_recipiente = st.number_input("Multiplicador para Recipientes:", min_value=1.0, value=1.5, step=0.1)
        with col_m2:
            margen_molde = st.number_input("Multiplicador para Moldes:", min_value=1.0, value=2.0, step=0.1)
        with col_m3:
            margen_refill_cfg = st.number_input("Multiplicador para Refill:", min_value=1.0, value=float(margen_refill_fijado), step=0.1)
            
        if st.button("🔄 Recalcular Costos y Precios Sugeridos", type="secondary"):
            # Actualizar margen de refill
            if (df_insumos["id_insumo"] == "CFG-MARGEN-REF").any():
                df_insumos.loc[df_insumos["id_insumo"] == "CFG-MARGEN-REF", "costo_unitario"] = margen_refill_cfg
            else:
                df_insumos = pd.concat([df_insumos, pd.DataFrame([{
                    "id_insumo": "CFG-MARGEN-REF",
                    "nombre": "MULTIPLICADOR MARGEN REFILL",
                    "categoria": "Config",
                    "unidad_medida": "ratio",
                    "costo_unitario": margen_refill_cfg
                }])], ignore_index=True)
            escribir_hoja("insumos", df_insumos)
            
            # Recalcular productos
            for idx, r in df_productos.iterrows():
                if r["id_producto"] == "REFILL":
                    continue
                tipo = r["tipo_linea"]
                cera = float(r["gramos_cera"] or 0)
                env = float(r["costo_recipiente_o_molde"] or 0)
                
                if tipo == "Recipiente":
                    c_calc = env + (cera * cera_bpf_end) + esencia + pabilo + cinta + ojalillo + caja_grande
                    sug = math.ceil(c_calc * margen_recipiente / 10.0) * 10
                elif tipo == "Molde":
                    c_calc = (env / 30.0) + (cera * cera_apf) + esencia + color + pabilo + ojalillo
                    sug = math.ceil(c_calc * margen_molde / 10.0) * 10
                else:
                    c_calc = env
                    sug = math.ceil(c_calc * margen_recipiente / 10.0) * 10
                    
                df_productos.at[idx, "costo_fabricacion"] = round(c_calc, 0)
                df_productos.at[idx, "precio_venta_sugerido"] = sug
                
            escribir_hoja("productos", df_productos)
            st.success("¡Costos, precios sugeridos y márgenes actualizados en Google Sheets!")
            st.rerun()
            
        st.write("---")
        st.markdown("##### Ajuste manual de Precios de Venta Actuales")
        df_ajuste = df_productos[df_productos["id_producto"] != "REFILL"][["id_producto", "nombre", "tipo_linea", "costo_fabricacion", "precio_venta_sugerido", "precio_venta_actual"]].copy()
        
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
            for _, r in df_ajuste_edit.iterrows():
                df_productos.loc[df_productos["id_producto"] == r["id_producto"], "precio_venta_actual"] = float(r["precio_venta_actual"])
            escribir_hoja("productos", df_productos)
            st.success("¡Precios de venta al público guardados en Google Sheets!")
            st.rerun()

    # 3. EXPLORADOR DE TABLAS
    with subtab_tablas:
        st.markdown("##### Visualizador de Hojas de Google Sheets")
        tabla_sel = st.selectbox("Seleccioná la hoja que querés inspeccionar:", ["productos", "ventas", "movimientos_stock", "insumos"])
        df_raw = leer_hoja(tabla_sel)
        st.dataframe(df_raw, use_container_width=True)
        st.caption(f"Mostrando {len(df_raw)} registros de la hoja '{tabla_sel}'.")