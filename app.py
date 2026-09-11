# --- SEGURIDAD Y ACCESO ---
def verificar_acceso():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.title("🔒 Acceso Restringido - Bellas Velas")
        col1, _ = st.columns([1, 1])
        with col1:
            clave_ingresada = st.text_input("Ingresá la contraseña de acceso:", type="password")
            if st.button("Ingresar 🔑", type="primary"):
                # ACÁ DEFINÍS TU CONTRASEÑA (cambiá 'velas2024' por la que vos quieras)
                if clave_ingresada == "velas2024":
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
        return False
    return True

if not verificar_acceso():
    st.stop()  # Detiene la ejecución acá si no puso la clave correcta