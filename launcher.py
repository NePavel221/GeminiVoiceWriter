import sys
import traceback

try:
    with open("launcher_debug.log", "w") as f:
        f.write("Launcher started.\n")

    print("Importing main...")
    import main
    
    with open("launcher_debug.log", "a") as f:
        f.write("Main imported. Running main.main()...\n")
        
    main.main()
    
except Exception as e:
    msg = f"CRASH in launcher: {e}\n"
    print(msg)
    with open("launcher_debug.log", "a") as f:
        f.write(msg)
        traceback.print_exc(file=f)
    input("Press Enter to exit...") # Keep terminal open if possible
