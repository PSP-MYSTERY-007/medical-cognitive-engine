import pandas as pd
import time

def test_primekg_logic(target_drug):
    print(f"🔍 Testing Knowledge Graph Engine for: {target_drug}")
    start_time = time.time()
    
    # Path to your PrimeKG file
    kg_path = "knowledge_graph/data/kg.csv"
    
    try:
        # Optimization: Use low_memory and only load necessary columns
        # PrimeKG columns: relation, x_type, x_name, y_type, y_name
        df = pd.read_csv(kg_path, low_memory=False)
        
        # 1. Check for Contraindications (Pharmacopoeia Safety)
        contra_df = df[
            (df['x_name'].str.lower() == target_drug.lower()) & 
            (df['relation'] == 'contraindication')
        ]
        
        # 2. Check for Indications (What it treats)
        indication_df = df[
            (df['x_name'].str.lower() == target_drug.lower()) & 
            (df['relation'] == 'indication')
        ]

        print(f"✅ Data Load & Search took: {time.time() - start_time:.2f} seconds")
        print("-" * 30)
        
        if not contra_df.empty:
            print(f"🛑 CONTRAINDICATIONS FOUND for {target_drug}:")
            for item in contra_df['y_name'].unique():
                print(f"   - {item}")
        else:
            print(f"ℹ️ No hard contraindications found for {target_drug} in PrimeKG.")

        if not indication_df.empty:
            print(f"\n💊 APPROVED INDICATIONS for {target_drug}:")
            for item in indication_df['y_name'].unique():
                print(f"   - {item}")
                
    except FileNotFoundError:
        print("❌ Error: kg.csv not found. Please download it to trialcpg/knowledge_graph/data/")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    # Test with a high-alert drug like 'Metformin' or 'Warfarin'
    test_primekg_logic("doxacylin")