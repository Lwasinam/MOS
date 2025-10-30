import streamlit as st
import pandas as pd
from pathlib import Path
import csv
import os
import uuid  # Added for automatic user ID generation

# --- Configuration ---
# The app will look for audio files in this folder.
# You MUST create this folder in the same directory as the app.
AUDIO_FOLDER = Path("audio_files")

# This is where the ratings will be saved.
RATINGS_FILE = Path("mos_ratings.csv")

# --- New file for the MOS summary ---
MOS_SUMMARY_FILE = Path("mos_summary.csv")
# ---

# The 5-point MOS scale
RATING_SCALE = {
    "1: Bad": 1,
    "2: Poor": 2,
    "3: Fair": 3,
    "4: Good": 4,
    "5: Excellent": 5
}
CSV_HEADER = ["user_id", "audio_file", "rating"]

# --- Helper Functions ---

def setup_files():
    """Create the audio folder and ratings CSV if they don't exist."""
    # Create the audio folder if it's missing
    AUDIO_FOLDER.mkdir(exist_ok=True)
    
    # Create the CSV file with a header if it's missing
    if not RATINGS_FILE.exists():
        with open(RATINGS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
    
    # Note: We don't need to create the summary file; 
    # it will be created/overwritten by the update function.

def get_audio_files():
    """Get a sorted list of supported audio files from the folder."""
    supported_extensions = [".wav", ".mp3", ".ogg"]
    files = [
        f.name for f in AUDIO_FOLDER.iterdir() 
        if f.suffix.lower() in supported_extensions and f.is_file()
    ]
    files.sort()  # Ensure a consistent order for all users
    return files

# --- New function to calculate and save the MOS summary ---
def update_mos_summary():
    """
    Reads all ratings from the main CSV file, calculates the
    current MOS for each file, and saves it to a summary CSV.
    This file is overwritten each time to keep it up-to-date.
    """
    try:
        # Read all the ratings
        df = pd.read_csv(RATINGS_FILE)
        
        if df.empty:
            # Don't create an empty summary file
            return

        # Calculate MOS per file
        # Group by file and calculate the mean of the 'rating' column
        mos_df = df.groupby('audio_file')['rating'].mean().reset_index()
        mos_df = mos_df.rename(columns={'rating': 'MOS'})
        
        # Save the summary, overwriting the file
        mos_df.to_csv(MOS_SUMMARY_FILE, index=False, encoding='utf-8')
        
    except pd.errors.EmptyDataError:
        # This can happen if the file was just created and is empty
        pass
    except Exception as e:
        # Log this error to the console for the admin
        print(f"Error updating MOS summary: {e}")
# ---

def save_rating(user_id, audio_file, rating):
    """Append a new rating to the CSV file and update the MOS summary."""
    # 'a' mode means 'append'
    with open(RATINGS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, audio_file, rating])
    
    # --- After saving, trigger the summary update ---
    update_mos_summary()
    # ---

# --- Streamlit App UI ---

def main():
    st.set_page_config(layout="wide", page_title="MOS Audio Rating")
    st.title("🎧 Audio Quality (MOS) Rating Tool")

    # 1. Setup folders and files
    setup_files()
    audio_files = get_audio_files()

    if not audio_files:
        st.error(
            f"No audio files found in the '{AUDIO_FOLDER}' folder."
            " Please add some .wav, .mp3, or .ogg files and refresh."
        )
        st.stop()

    # 2. Initialize Streamlit's Session State
    # This is used to remember variables as the user interacts
    
    # --- Auto-generate User ID if not present ---
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{str(uuid.uuid4())[:8]}"
    # ---
        
    if 'current_audio_index' not in st.session_state:
        st.session_state.current_audio_index = 0
    if 'ratings_submitted' not in st.session_state:
        st.session_state.ratings_submitted = False

    # 3. User Identification
    st.sidebar.header("Your Information")
    # --- Removed text input, just display the auto-generated ID ---
    st.sidebar.success(f"Rating as: **{st.session_state.user_id}**")
    
    # --- Removed the check for empty user_id, as it's now auto-generated ---


    # 4. Rating Interface
    
    # Check if all files have been rated
    if st.session_state.current_audio_index >= len(audio_files):
        st.session_state.ratings_submitted = True
        
    if st.session_state.ratings_submitted:
        st.success("🎉 Thank you! You have rated all available audio files.")
        st.balloons()
        
        # Optionally show the *raw* results, but not the MOS summary
        if st.checkbox("Show All Submitted Ratings"):
            try:
                df = pd.read_csv(RATINGS_FILE)
                st.dataframe(df)
                
                # --- MOS calculation removed from the UI per your request ---
                
            except pd.errors.EmptyDataError:
                st.info("No ratings have been submitted yet.")
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
    # Using a form ensures that the rating is submitted with the button
    with st.form(key="mos_form"):
        st.subheader("Please rate the quality of the audio:")
        
        # Using radio buttons for the 5-point scale
        rating_label = st.radio(
            label="Rating (1=Bad, 5=Excellent)",
            options=RATING_SCALE.keys(),
            index=2,  # Default to '3: Fair'
            horizontal=True
        )
        
        # Submit button for the form
        submit_button = st.form_submit_button(label="Submit Rating and Go to Next")

    # 5. Form Submission Logic
    if submit_button:
        # Get the numeric rating (e.g., 1, 2, 3, 4, or 5)
        selected_rating = RATING_SCALE[rating_label]
        
        # Save the rating to the CSV
        save_rating(
            st.session_state.user_id, 
            current_file_name, 
            selected_rating
        )
        
        st.toast(
            f"Rating for '{current_file_name}' saved!",
            icon="✅"
        )
        
        # Move to the next file by incrementing the index
        st.session_state.current_audio_index += 1
        
        # Check if we just finished the last file
        if st.session_state.current_audio_index == len(audio_files):
            st.session_state.ratings_submitted = True
        
        # Rerun the script to show the next file or the completion message
        st.rerun()

if __name__ == "__main__":
    main()



