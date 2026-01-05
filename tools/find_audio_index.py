import pyaudio

p = pyaudio.PyAudio()
print("Searching for 'USB Audio Device' (Handset)...")

found_index = -1
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"Index {i}: {info['name']}")
    if "USB Audio Device" in info['name']:
        found_index = i
        print(f"--> FOUND! Index: {i}")

p.terminate()
