try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.multioutput import MultiOutputClassifier
    print("Imports OK")
    
    clf = MultiOutputClassifier(RandomForestClassifier())
    print("Class init OK")
except Exception as e:
    print(f"Error: {e}")
