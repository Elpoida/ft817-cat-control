import cat

print("bcd", cat.bcd(1406000, 8).hex(), cat.from_bcd(cat.bcd(1406000, 8)))
print("set_freq", cat.set_freq(14060000).hex(" "))
print("layout", cat.mem_layout("817"), cat.mem_addr(1, "817"))
record = cat.encode_memory(145500000, "FM", "CALL")
print("memory", record.hex(), cat.decode_memory(record, 1))
print("detect", cat.detect_model(7100000, 2), cat.detect_model(7100000, 3))
print("band", cat.band_of(7100000, "817"), cat.band_record(7100000, "817", "A"))
