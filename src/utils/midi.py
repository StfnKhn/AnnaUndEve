# Utility functions for the Classical Music MIDI as CSV dataset import os
import pandas as pd
import mido
from mido import MidiFile, MetaMessage, Message, MidiTrack


def mid_to_df_info(path: str) -> None:
    """Convert a midi file to a csv file"""
    df = pd.DataFrame()
    mid = mid = MidiFile(path)

    for n_track, track in enumerate(mid.tracks):
        track_df = pd.DataFrame()
        time = 0

        # place all midi messages into a dataframe
        for msg in track:
            msg_dict = msg.__dict__
            msg_dict["meta"] = int(isinstance(msg, MetaMessage))
            msg_dict["track"] = n_track

            if "time" not in msg_dict:
                continue

            time += int(msg_dict["time"])
            msg_dict["tick"] = time

            # delete redundant keys
            for k in ["name", "text"]:
                if k in msg_dict:
                    del msg_dict[k]

            track_df = pd.concat(
                [track_df, pd.DataFrame([msg_dict])], ignore_index=True
            )

        # merge song dataframe with track dataframe
        if df.shape[0] > 0:
            df = pd.merge(df, track_df, how="outer")
        else:
            df = track_df

    for col in df.columns:
        if df[col].dtype == "float64":
            df[col] = df[col].astype("Int64")

    return df


def midi_to_df(path):
    # Read the MIDI file
    midi = MidiFile(path)

    # Calculate ticks per beat (resolution of the MIDI file)
    ticks_per_beat = midi.ticks_per_beat
    print("Ticks per beat:", ticks_per_beat)

    # List to hold all track data
    all_track_data = []

    # Track counter
    track_number = 0

    # Iterate over each track in the MIDI file
    for track in midi.tracks:
        track_number += 1
        track_name = f"Track{track_number}"

        # Absolute time in ticks
        absolute_time_ticks = 0

        # Process each message in the track
        for msg in track:
            absolute_time_ticks += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                # Note start
                note_start = absolute_time_ticks

            if msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                # Note end - calculate duration and add to track data
                note_end = absolute_time_ticks
                note_duration = note_end - note_start  # Keep the duration in ticks
                note_value = msg.note
                all_track_data.append({'track': track_name, 'time': note_start, 'duration': note_duration, 'note': note_value})

    # Convert to DataFrame
    df = pd.DataFrame(all_track_data)

    return df


def bpm_to_tempo(bpm):
    return int(60 * 1e6 / bpm)


def create_midi(df, output_file, bpm=120, ticks_per_beat=960, time_signature=(4, 4), clocks_per_click=48):
    # Create a new MIDI file
    midi = MidiFile(ticks_per_beat=ticks_per_beat)

    # Set the tempo
    tempo = bpm_to_tempo(bpm)

    # Create a meta track for tempo and time signature
    meta_track = MidiTrack()
    midi.tracks.append(meta_track)

    # Add the set_tempo MetaMessage to the meta track
    meta_track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))

    # Add the time_signature MetaMessage
    numerator, denominator = time_signature
    meta_track.append(mido.MetaMessage('time_signature', numerator=numerator, 
                                       denominator=denominator, clocks_per_click=clocks_per_click, 
                                       notated_32nd_notes_per_beat=8, time=0))

    # Group notes by track
    grouped = df.groupby('track')

    # Iterate over each track
    for track_name, notes in grouped:
        # Create a new track and add it to the MIDI file
        track = MidiTrack()
        midi.tracks.append(track)

        # Add a track name MetaMessage
        track.append(mido.MetaMessage('track_name', name=track_name, time=0))

        # Initialize the last event time and the previous note end time
        last_event_time_ticks = 0
        prev_note_end_time_ticks = 0

        # Iterate through the DataFrame rows for this track
        for _, note_info in notes.iterrows():
            note_time_ticks = int(note_info['time'])
            note_duration_ticks = int(note_info['duration'])
            note = note_info['note']

            # Handle negative time interval by adjusting the duration of the previous note
            if note_time_ticks < prev_note_end_time_ticks:
                # Adjust the duration of the previous note
                adjustment = prev_note_end_time_ticks - note_time_ticks
                if last_event_time_ticks >= adjustment:
                    last_event_time_ticks -= adjustment
                else:
                    # If adjustment is not possible, raise an error
                    raise ValueError(f"Unable to adjust the duration of the previous note at time {prev_note_end_time_ticks/ticks_per_beat}.")

            # Calculate the time since the last event
            time_since_last_event_ticks = note_time_ticks - last_event_time_ticks

            # Add note_on and note_off messages
            track.append(Message('note_on', note=note, velocity=64, time=time_since_last_event_ticks))
            track.append(Message('note_off', note=note, velocity=64, time=note_duration_ticks))

            # Update the last event time and the previous note end time
            last_event_time_ticks = note_time_ticks
            prev_note_end_time_ticks = note_time_ticks + note_duration_ticks

    # Save the Midi file
    midi.save(output_file)
