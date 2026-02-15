import duckdb
import re

class MedicalGraphEngine:
    def __init__(self):
        self.db_path = 'medicalchatbot/knowledge_graph/data/kg_index.db'
        self._con = duckdb.connect(self.db_path, read_only=True)
        # Pre-compile a list of drugs for faster regex matching
        self.drug_list = ["Metformin", "Warfarin", "Lisinopril", "Aspirin", "Apixaban"] 
        self.pattern = re.compile(r'\b(' + '|'.join(self.drug_list) + r')\b', re.IGNORECASE)

    def get_pharmacopoeia_alerts(self, text):
        """Checks ANY text (query or answer) for drug interactions."""
        found = list(set(self.pattern.findall(text))) # Find unique drugs
        
        if not found: 
            return []

        results = []
        for drug in found:
            # Normalize casing for DB lookup
            formatted_drug = drug.capitalize()
            rows = self._con.execute("""
                SELECT relation, y_name 
                FROM primekg 
                WHERE x_name = ? 
                AND relation IN ('contraindication', 'indication')
            """, [formatted_drug]).fetchall()
            
            for rel, target in rows:
                results.append(f"🛡️ **KG ALERT:** {formatted_drug} {rel} -> {target}")
        
        return results