import streamlit as st
import pandas as pd
from pathlib import Path
import uuid
from supabase import create_client, Client

# --- Configuration ---
# The app will look for audio files in this folder.
AUDIO_FOLDER = Path("audio_files")

# The 5-point MOS scale
RATING_SCALE = {
    "1: Bad": 1,
    "2: Poor": 2,
    "3: Fair": 3,
    "4: Good": 4,
    "5: Excellent": 5
}

# --- Helper Functions ---

@st.cache_resource
def init_supabase_client():
    """Initialize and return the Supabase client."""
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}. Did you add your credentials to st.secrets?")
        st.stop()

def setup_audio_folder():
    """Create the audio folder if it doesn't exist."""
    AUDIO_FOLDER.mkdir(exist_ok=True)

def get_audio_files():
    """Get a sorted list of supported audio files from the folder."""
    supported_extensions = [".wav", ".mp3", ".ogg"]
    files = [
        f.name for f in AUDIO_FOLDER.iterdir()
        if f.suffix.lower() in supported_extensions and f.is_file()
    ]
    files.sort()  # Ensure a consistent order for all users
    return files

def save_rating_to_supabase(supabase: Client, user_id, audio_file, rating):
    """Append a new rating to the Supabase table."""
    try:
        response = supabase.table("mos_ratings").insert({
            "user_id": user_id,
            "audio_file": audio_file,
            "rating": rating
        }).execute()
        
        return True
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return False

def update_mos_for_file(supabase: Client, audio_file):
    """Update the MOS summary for a specific audio file."""
    try:
        # Get all ratings for this specific audio file
        response = supabase.table("mos_ratings")\
            .select("rating")\
            .eq("audio_file", audio_file)\
            .execute()
        
        if not response.data:
            return False
        
        ratings = [r['rating'] for r in response.data]
        mos_score = sum(ratings) / len(ratings)
        rating_count = len(ratings)
        
        # Check if this audio file already has a summary entry
        existing = supabase.table("mos_summary")\
            .select("id")\
            .eq("audio_file", audio_file)\
            .execute()
        
        if existing.data:
            # Update existing record
            supabase.table("mos_summary")\
                .update({
                    "mos_score": mos_score,
                    "rating_count": rating_count
                })\
                .eq("audio_file", audio_file)\
                .execute()
        else:
            # Insert new record
            supabase.table("mos_summary").insert({
                "audio_file": audio_file,
                "mos_score": mos_score,
                "rating_count": rating_count
            }).execute()
        
        return True
    except Exception as e:
        # Log error but don't show to user to avoid disruption
        print(f"Error updating MOS summary: {e}")
        return False

# --- Streamlit App UI ---

def main():
    st.set_page_config(layout="wide", page_title="MOS Audio Rating")
    st.title("🎧 Audio Quality (MOS) Rating Tool")

    # 1. Initialize Supabase Connection
    supabase = init_supabase_client()
    
    # 2. Setup audio folder
    setup_audio_folder()
    audio_files = get_audio_files()

    if not audio_files:
        st.error(
            f"No audio files found in the '{AUDIO_FOLDER}' folder."
            " Please add some .wav, .mp3, or .ogg files and refresh."
        )
        st.stop()

    # 3. Initialize Streamlit's Session State
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{str(uuid.uuid4())[:8]}"
    if 'current_audio_index' not in st.session_state:
        st.session_state.current_audio_index = 0
    if 'ratings_submitted' not in st.session_state:
        st.session_state.ratings_submitted = False

    # 4. User Identification
    st.sidebar.header("Your Information")
    st.sidebar.success(f"Rating as: **{st.session_state.user_id}**")

    # 5. Rating Interface
    
    # Check if all files have been rated
    if st.session_state.current_audio_index >= len(audio_files):
        st.session_state.ratings_submitted = True
        
    if st.session_state.ratings_submitted:
        st.success("🎉 Thank you! You have rated all available audio files.")
        st.balloons()
        st.info("Your ratings have been saved. You may close this page.")
        st.stop()

    # Get the current file to rate
    current_file_name = audio_files[st.session_state.current_audio_index]
    current_file_path = AUDIO_FOLDER / current_file_name

    st.header(f"Rating Audio File: `{current_file_name}`")
    st.info(
        f"File {st.session_state.current_audio_index + 1} of {len(audio_files)}"
    )

    # Display audio player
    try:
        audio_bytes = current_file_path.read_bytes()
        st.audio(audio_bytes)
    except Exception as e:
        st.error(f"Error loading audio file: {e}")
        st.stop()

    # Rating form
    with st.form(key="mos_form"):
        st.subheader("Please rate the quality of the audio:")
        
        rating_label = st.radio(
            label="Rating (1=Bad, 5=Excellent)",
            options=RATING_SCALE.keys(),
            index=2,  # Default to '3: Fair'
            horizontal=True
        )
        
        submit_button = st.form_submit_button(label="Submit Rating and Go to Next")

    # 6. Form Submission Logic
    if submit_button:
        selected_rating = RATING_SCALE[rating_label]
        
        # Save the rating to Supabase
        success = save_rating_to_supabase(
            supabase,
            st.session_state.user_id,
            current_file_name,
            selected_rating
        )
        
        if success:
            st.toast(
                f"Rating for '{current_file_name}' saved!",
                icon="✅"
            )
            
            # Update the MOS summary for this specific file (non-blocking)
            update_mos_for_file(supabase, current_file_name)
            
            # Move to the next file
            st.session_state.current_audio_index += 1
            
            if st.session_state.current_audio_index == len(audio_files):
                st.session_state.ratings_submitted = True
            
            st.rerun()
        else:
            st.toast("Failed to save rating.", icon="❌")


if __name__ == "__main__":
    main()