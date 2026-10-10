import streamlit as st
import pymupdf
from google import genai
import edge_tts
import asyncio
import os
from dotenv import load_dotenv

# Load API key
load_dotenv()
API_KEY = os.getenv("API_KEY")
client = genai.Client(api_key=API_KEY)

async def generate_audio(text, voice_code, output_filename):
    communicate = edge_tts.Communicate(text, voice_code)
    await communicate.save(output_filename)

def chunk_text(text, chunk_size=20000):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

# --- Streamlit Web UI ---
st.set_page_config(page_title="AI Study Dashboard", page_icon="🎓", layout="wide")

# --- Sidebar Navigation ---
st.sidebar.title("📚 Navigation")
app_mode = st.sidebar.radio("Choose Mode", ["Create New Notes", "My Study Library"])

# Ensure the Subjects directory exists
os.makedirs("Subjects", exist_ok=True)

if app_mode == "Create New Notes":
    st.title("🎓 Smart Study Dashboard")
    st.write("Upload your lecture notes to generate and organize your study materials.")

    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox("Language", ["Bahasa Melayu", "English"])
    with col2:
        if language == "Bahasa Melayu":
            voices = {"Female (Yasmin)": "ms-MY-YasminNeural", "Male (Osman)": "ms-MY-OsmanNeural"}
        else:
            voices = {"US Female (Aria)": "en-US-AriaNeural", "US Male (Guy)": "en-US-GuyNeural"}
        selected_voice_name = st.selectbox("Voice", list(voices.keys()))
        selected_voice_code = voices[selected_voice_name]

    st.divider()
    
    st.subheader("📁 Organization")
    subject_name = st.text_input("Chapter or Subject Name (e.g., Data Coms Chap 1)", value="General_Notes")

    uploaded_file = st.file_uploader("Upload Full PDF Lecture Notes", type="pdf")

    if uploaded_file is not None:
        if st.button("Generate Study Dashboard"):
            
            safe_folder_name = "".join([c for c in subject_name if c.isalnum() or c.isspace()]).rstrip().replace(" ", "_")
            if not safe_folder_name:
                safe_folder_name = "General_Notes"
                
            subject_dir = os.path.join("Subjects", safe_folder_name)
            os.makedirs(subject_dir, exist_ok=True)
            
            with st.spinner("Extracting entire text from PDF..."):
                doc = pymupdf.open(stream=uploaded_file.read(), filetype="pdf")
                raw_text = ""
                for page in doc:
                    raw_text += page.get_text()
                    
                text_chunks = chunk_text(raw_text)
                
            master_script = ""
            master_points = ""
            master_flashcards = ""
            
            progress_bar = st.progress(0)
            st.write(f"Analyzing {len(text_chunks)} sections of your document...")
            
            for i, chunk in enumerate(text_chunks):
                prompt = f"""
                You are an expert university tutor. Analyze the following text and provide your response in EXACTLY three sections separated by '|||'.
                Everything must be written in fluent {language}.

                Section 1: PODCAST SCRIPT
                Write a conversational, easy-to-listen-to podcast script explaining the concepts.

                Section 2: KEY POINTS
                Extract 3 to 5 critical bullet points.

                Section 3: FLASHCARDS
                Create 3 Question and Answer pairs formatted as:
                **Q:** [Question]
                **A:** [Answer]
                
                Text section:
                {chunk} 
                
                Format your response EXACTLY like this:
                [Podcast script here]
                |||
                [Bullet points here]
                |||
                [Flashcards here]
                """
                
                try:
                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=prompt
                    )
                except Exception as e:
                    st.error("Google's AI servers are currently too busy. Please wait a minute and try again!")
                    st.stop()
                
                try:
                    parts = response.text.split("|||")
                    master_script += parts[0].strip() + "\n\n"
                    master_points += parts[1].strip() + "\n\n"
                    master_flashcards += parts[2].strip() + "\n\n"
                except Exception as e:
                    master_script += response.text + "\n\n"
                
                progress_bar.progress((i + 1) / len(text_chunks))
                
            with st.spinner(f"Recording your podcast using {selected_voice_name}..."):
                output_audio_path = os.path.join(subject_dir, "study_podcast.mp3")
                asyncio.run(generate_audio(master_script, selected_voice_code, output_audio_path))
                
                output_text_path = os.path.join(subject_dir, "study_notes.txt")
                with open(output_text_path, "w", encoding="utf-8") as text_file:
                    text_file.write("--- KEY TAKEAWAYS ---\n")
                    text_file.write(master_points + "\n\n")
                    text_file.write("--- FLASHCARDS ---\n")
                    text_file.write(master_flashcards)
                
            st.success(f"Dashboard Ready! Files saved securely in the '{safe_folder_name}' folder. Switch to 'My Study Library' to view them anytime.")

elif app_mode == "My Study Library":
    st.title("📚 My Study Library")
    
    # Check what folders exist in the Subjects directory
    existing_subjects = [f for f in os.listdir("Subjects") if os.path.isdir(os.path.join("Subjects", f))]
    
    if not existing_subjects:
        st.info("Your library is empty. Go to 'Create New Notes' to generate your first study set.")
    else:
        # Create a dropdown to select past subjects
        selected_subject = st.selectbox("Select a Chapter to Review", existing_subjects)
        
        subject_dir = os.path.join("Subjects", selected_subject)
        audio_path = os.path.join(subject_dir, "study_podcast.mp3")
        text_path = os.path.join(subject_dir, "study_notes.txt")
        
        if os.path.exists(audio_path) and os.path.exists(text_path):
            st.subheader(f"🎧 {selected_subject} Podcast")
            st.audio(audio_path)
            
            # Read the saved text file and split it back into Points and Flashcards
            with open(text_path, "r", encoding="utf-8") as f:
                saved_content = f.read()
                
            try:
                points_part, flashcards_part = saved_content.split("--- FLASHCARDS ---\n")
                points_part = points_part.replace("--- KEY TAKEAWAYS ---\n", "")
            except ValueError:
                # Fallback if formatting was slightly off
                points_part = saved_content
                flashcards_part = ""
            
            st.divider()
            
            col_points, col_cards = st.columns(2)
            with col_points:
                st.subheader("📝 Key Takeaways")
                st.markdown(points_part)
                
            with col_cards:
                st.subheader("🧠 Flashcards")
                st.warning("Test your knowledge. Click to reveal answers.")
                
                cards = flashcards_part.split("**Q:**")
                for card in cards:
                    if "**A:**" in card:
                        try:
                            question, answer = card.split("**A:**", 1)
                            with st.expander(f"Question: {question.strip()}"):
                                st.write(answer.strip())
                        except:
                            pass 
        else:
            st.error("Audio or text files are missing for this subject.")