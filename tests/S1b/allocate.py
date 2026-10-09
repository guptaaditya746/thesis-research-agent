try:
    value = " " * 10**11
    print("allocation=unexpected-success")
except MemoryError:
    print("allocation=MemoryError")
