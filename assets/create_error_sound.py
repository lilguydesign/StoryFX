import wave
import struct
import math
import os

sample_rate = 44100
duration = 0.6
frequency = 880.0
amplitude = 0.5

num_samples = int(sample_rate * duration)

output_path = "storyfx_error_alert.wav"

with wave.open(output_path, "w") as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)

    for i in range(num_samples):
        t = i / sample_rate
        value = int(amplitude * 32767.0 * math.sin(2 * math.pi * frequency * t))
        wav_file.writeframesraw(struct.pack("<h", value))

print("OK ! Fichier généré :", os.path.abspath(output_path))
