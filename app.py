import streamlit as st
import json
import os
from google import genai
from google.genai import types
from PIL import Image
from github import Github

# -------------------------------------------------------------
# CONFIGURÁ TUS CLAVES Y DATOS ACÁ ADENTRO ENTRE LAS COMILLAS:
API_KEY_GEMINI = "AQ.Ab8RN6K0eRkApfLMvSj7cHV20zZ_f6m7mcsvZG9MwDLGGfF0iw"
GITHUB_TOKEN = "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"
GITHUB_USUARIO = "4le01722"  # Ej: "juanperez"
GITHUB_REPO_NOMBRE = "mi-armario-ia"          # El nombre que le diste al repo
# -------------------------------------------------------------

# Conectar con GitHub e IA
g = Github(GITHUB_TOKEN)
repo_path = f"{GITHUB_USUARIO}/{GITHUB_REPO_NOMBRE}"
repo = g.get_repo(repo_path)
client = genai.Client(api_key=API_KEY_GEMINI)

# Funciones para leer y escribir en GitHub (nuestro disco rígido en la nube)
def cargar_armario_github():
    try:
        file_content = repo.get_contents("armario.json")
        return json.loads(file_content.decoded_content.decode("utf-8")), file_content.sha
    except Exception:
        # Si el archivo no existe en GitHub, lo creamos vacío
        repo.create_file("armario.json", "Crear armario inicial", "[]")
        return [], None

def guardar_armario_github(nuevo_armario, sha=None):
    contenido_string = json.dumps(nuevo_armario, indent=2, ensure_ascii=False)
    if sha:
        repo.update_file("armario.json", "Actualizar armario", contenido_string, sha)
    else:
        file_content = repo.get_contents("armario.json")
        repo.update_file("armario.json", "Actualizar armario", contenido_string, file_content.sha)

# Cargar el armario al inicio
armario, armario_sha = cargar_armario_github()

# Inicializar variables de estado de la página
if "outfit_actual" not in st.session_state:
    st.session_state.outfit_actual = None
if "historial_feedback" not in st.session_state:
    st.session_state.historial_feedback = []

# Pestañas de la app
tab1, tab2, tab3 = st.tabs(["👗 Mi Armario e IA", "➕ Agregar Ropa Automáticamente", "📦 Ver Mi Catálogo"])

# --- PESTAÑA 1: RECOMENDACIÓN DE OUTFITS ---
with tab1:
    st.title("👗 Mi Armario Inteligente")
    st.write("Decile a la IA cómo está el clima y armará tu combinación.")

    clima_input = st.text_input("¿Cómo está el día?", placeholder="Ej: hace frío pero no tanto / hace un calor infernal")

    if st.button("Generar Outfit 🎲"):
        if clima_input and list(armario):
            prompt = f"""
            Sos un asistente de moda personal. El usuario dice que el clima está: '{clima_input}'.
            Basándote ÚNICAMENTE en el siguiente catálogo de ropa en formato JSON, armá un outfit adecuado combinando las prendas.
            Devolvé el resultado estrictamente en formato JSON con una lista de los 'id' de las prendas elegidas bajo la clave 'outfit'.
            Catálogo: {json.dumps(armario)}
            """
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            resultado = json.loads(response.text)
            st.session_state.outfit_actual = resultado.get("outfit", [])
            st.session_state.historial_feedback = [] 
        elif not list(armario):
            st.warning("Tu armario está vacío en GitHub. ¡Agregá ropa en la otra pestaña!")
        else:
            st.warning("Por favor, escribí cómo está el clima.")

    if st.session_state.outfit_actual:
        st.subheader("Tu Outfit Sugerido:")
        cols = st.columns(len(st.session_state.outfit_actual))
        for i, prenda_id in enumerate(st.session_state.outfit_actual):
            prenda = next((p for p in armario if p["id"] == prenda_id), None)
            if prenda:
                with cols[i]:
                    st.write(f"**{prenda['nombre']}**")
                    # Enlace directo de la foto desde GitHub público
                    url_foto = f"https://raw.githubusercontent.com/{repo_path}/main/{prenda['foto_path']}"
                    st.image(url_foto, use_container_width=True)

        st.markdown("---")
        st.subheader("🔄 ¿No te convence algo?")
        feedback = st.text_input("¿Qué querés cambiar?", placeholder="Ej: No me gusta el buzo negro, cambialo")
        
        if st.button("Modificar Outfit 🛠️"):
            if feedback:
                st.session_state.historial_feedback.append(feedback)
                prompt_cambio = f"""
                El usuario tenía este outfit actual: {st.session_state.outfit_actual}.
                El clima sigue siendo: '{clima_input}'.
                El usuario quiere una modificación: '{feedback}'.
                Historial de cambios: {st.session_state.historial_feedback}.
                Modificá el outfit reemplazando la prenda solicitada por otra del catálogo. Devolvé formato JSON con clave 'outfit'.
                Catálogo: {json.dumps(armario)}
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_cambio,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                resultado = json.loads(response.text)
                st.session_state.outfit_actual = resultado.get("outfit", [])
                st.rerun()

# --- PESTAÑA 2: AGREGAR ROPA CON IA ---
with tab2:
    st.title("📸 Escáner de Ropa Inteligente")
    st.write("Subí la foto de una prenda. Gemini la va a analizar y se guardará en tu GitHub.")

    archivo_subido = st.file_uploader("Elegí la foto de tu prenda", type=["jpg", "jpeg", "png"])

    if archivo_subido is not None:
        imagen = Image.open(archivo_subido)
        st.image(imagen, caption="Prenda a escanear", width=250)

        nombre_archivo_limpio = archivo_subido.name.lower().replace(" ", "_")
        ruta_github_foto = f"ropa/{nombre_archivo_limpio}"

        if st.button("Analizar y Guardar en Internet 🧠"):
            with st.spinner("Subiendo foto y analizando con IA..."):
                # Convertir imagen a bytes para mandarla a GitHub
                archivo_subido.seek(0)
                foto_bytes = archivo_subido.read()
                
                # Guardar la foto en el repositorio de GitHub de forma directa
                try:
                    repo.create_file(ruta_github_foto, f"Agregar foto {nombre_archivo_limpio}", foto_bytes)
                except Exception:
                    # Si ya existía, la actualizamos sacando el SHA
                    contents = repo.get_contents(ruta_github_foto)
                    repo.update_file(ruta_github_foto, f"Actualizar foto {nombre_archivo_limpio}", foto_bytes, contents.sha)

                id_sugerido = os.path.splitext(nombre_archivo_limpio)[0]

                prompt_visual = f"""
                Analizá esta imagen de una prenda de ropa y devolvé sus características en formato JSON estricto.
                Usá exactamente las siguientes claves:
                - "id": Deberá ser obligatoriamente "{id_sugerido}"
                - "nombre": Un nombre descriptivo y corto de la prenda (Ej: "Campera puffer negra").
                - "categoria": Elegí una entre: "remera", "pantalon", "abrigo", "calzado", "accesorio".
                - "abrigo": Clasificá el nivel de abrigo eligiendo únicamente entre: "bajo", "medio", "alto".
                - "color": El color principal que predomina en la prenda.
                - "foto_path": Deberá ser obligatoriamente "{ruta_github_foto}"
                """

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[imagen, prompt_visual],
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )

                try:
                    datos_prenda = json.loads(response.text)
                    armario = [p for p in armario if p["id"] != datos_prenda["id"]]
                    armario.append(datos_prenda)
                    guardar_armario_github(armario, armario_sha)

                    st.success(f"¡Guardada en la nube! La IA la clasificó como: **{datos_prenda['nombre']}**")
                    st.json(datos_prenda)
                except Exception as e:
                    st.error("Hubo un error al procesar el JSON de la IA.")

# --- PESTAÑA 3: VER TODO EL CATÁLOGO ---
with tab3:
    st.title("📦 Mi Vestidor Completo")
    st.write(f"Actualmente tenés **{len(armario)}** prendas registradas en internet.")
    
    if not armario:
        st.info("Todavía no hay prendas en la nube. ¡Agregá una en la pestaña anterior!")
    else:
        columnas_grilla = st.columns(4)
        for index, prenda in enumerate(armario):
            with columnas_grilla[index % 4]:
                st.markdown(f"### {prenda['nombre']}")
                url_foto = f"https://raw.githubusercontent.com/{repo_path}/main/{prenda['foto_path']}"
                st.image(url_foto, use_container_width=True)
                
                st.caption(f"**Categoría:** {prenda['categoria'].capitalize()}")
                st.caption(f"**Abrigo:** {prenda['abrigo'].capitalize()}")
                st.caption(f"**Color:** {prenda['color'].capitalize()}")
                
                if st.button("🗑️ Eliminar", key=f"del_{prenda['id']}", type="primary"):
                    nuevo_armario = [p for p in armario if p["id"] != prenda["id"]]
                    guardar_armario_github(nuevo_armario, armario_sha)
                    
                    # Intentar borrar también la foto física en GitHub para no acumular basura
                    try:
                        contents = repo.get_contents(prenda["foto_path"])
                        repo.delete_file(prenda["foto_path"], f"Borrar foto {prenda['id']}", contents.sha)
                    except Exception:
                        pass
                        
                    if st.session_state.outfit_actual and prenda["id"] in st.session_state.outfit_actual:
                        st.session_state.outfit_actual = None
                        
                    st.success(f"Eliminaste {prenda['nombre']}")
                    st.rerun()
                st.markdown("---")