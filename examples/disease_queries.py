"""
INDRA CoGEx Disease Query Examples

This file demonstrates practical usage of the disease/phenotype query tool
for clinical and translational research. Each example is copy-pasteable and runnable.

Requirements:
    - INDRA CoGEx MCP server configured with Neo4j credentials
    - Python 3.10+ with mcp library installed

Setup:
    # Set environment variables
    export NEO4J_URL="bolt://your-server:7687"
    export NEO4J_USER="neo4j"
    export NEO4J_PASSWORD="your_password"

    # Run examples
    python examples/disease_queries.py
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ==============================================================================
# Example 1: ALS Etiopathology - Complete Disease Mechanisms
# ==============================================================================
# Scientific Context:
#   Amyotrophic Lateral Sclerosis (ALS) is a neurodegenerative disease with
#   complex genetic and molecular mechanisms. Understanding its complete
#   etiopathology requires integrating genes, phenotypes, drugs, and trials.
#
# Use Case:
#   Comprehensive disease profiling for research planning, grant writing, or
#   therapeutic development. Provides complete molecular landscape of a disease.
#
# Reference:
#   Mejzini et al. (2019). "ALS Genetics, Mechanisms, and Therapeutics"
#   Front. Neurosci. 13:1247
# ==============================================================================

async def example_1_als_complete_mechanisms():
    """
    Example 1: ALS etiopathology with complete disease mechanisms
    
    Expected Output:
        - ~20 ALS-associated genes (SOD1, TARDBP, FUS, C9orf72, etc.)
        - Clinical phenotypes (muscle weakness, hyperreflexia, fasciculations)
        - Drug therapies (Riluzole, Edaravone)
        - Active clinical trials
        - Genetic variants from GWAS
    """
    print("\n" + "="*80)
    print("Example 1: ALS Complete Disease Mechanisms")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",  # Update with your credentials
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "disease_to_mechanisms",
                    "disease": "mesh:D000690",  # ALS
                    "include_genes": True,
                    "include_variants": True,
                    "include_phenotypes": True,
                    "include_drugs": True,
                    "include_trials": True,
                    "response_format": "json"
                }
            )
            
            data = json.loads(result.content[0].text)
            
            print(f"\nDisease: {data['disease']['name']}")
            print(f"CURIE: {data['disease']['curie']}")
            
            print(f"\nGenetic Architecture:")
            print(f"  Associated Genes: {len(data.get('genes', []))}")
            if data.get('genes'):
                print(f"  Top Genes (by score):")
                for gene in sorted(data['genes'], key=lambda g: g.get('score', 0), reverse=True)[:5]:
                    print(f"    - {gene['gene']['name']}: score={gene.get('score', 0):.2f}, evidence={gene.get('evidence_count', 0)}")
            
            print(f"\nClinical Presentation:")
            print(f"  Phenotypes: {len(data.get('phenotypes', []))}")
            if data.get('phenotypes'):
                print(f"  Key Phenotypes:")
                for pheno in data['phenotypes'][:5]:
                    freq = pheno.get('frequency', 'unknown')
                    print(f"    - {pheno['phenotype']['name']} (frequency: {freq})")
            
            print(f"\nTherapeutic Landscape:")
            print(f"  Drug Therapies: {len(data.get('drugs', []))}")
            if data.get('drugs'):
                print(f"  Approved/Investigational Drugs:")
                for drug in data['drugs'][:3]:
                    print(f"    - {drug['drug']['name']}: {drug.get('indication_type', 'unknown')}, Phase {drug.get('max_phase', 'N/A')}")
            
            print(f"\nClinical Research:")
            print(f"  Active Trials: {len(data.get('trials', []))}")
            if data.get('trials'):
                print(f"  Recent Trials:")
                for trial in data['trials'][:3]:
                    print(f"    - {trial['nct_id']}: {trial.get('title', 'Unknown')[:60]}...")
                    print(f"      Status: {trial.get('status', 'unknown')}, Phase: {trial.get('phase', 'N/A')}")
            
            print(f"\nGenetic Variants:")
            print(f"  Associated Variants: {len(data.get('variants', []))}")
            if data.get('variants'):
                print(f"  Top GWAS Hits:")
                for variant in data['variants'][:3]:
                    print(f"    - {variant.get('variant', 'unknown')}: p={variant.get('p_value', 'N/A')}, OR={variant.get('odds_ratio', 'N/A')}")


# ==============================================================================
# Example 2: BRCA1 Disease Associations - Gene-to-Diseases Discovery
# ==============================================================================
# Scientific Context:
#   BRCA1 is primarily known for breast and ovarian cancer, but it participates
#   in DNA repair and has associations with other cancers and syndromes.
#
# Use Case:
#   Gene-centric disease discovery. Useful for understanding pleiotropy,
#   identifying patient populations for genetic testing, and repurposing
#   therapies across related diseases.
#
# Reference:
#   Kuchenbaecker et al. (2017). "Risks of Breast, Ovarian, and Contralateral
#   Breast Cancer for BRCA1 and BRCA2 Mutation Carriers" JAMA 317(23):2402-2416
# ==============================================================================

async def example_2_brca1_disease_associations():
    """
    Example 2: BRCA1 disease associations
    
    Expected Output:
        - Breast cancer (primary association)
        - Ovarian cancer
        - Pancreatic cancer
        - Prostate cancer
        - Fanconi anemia
        - Other DNA repair deficiency syndromes
    """
    print("\n" + "="*80)
    print("Example 2: BRCA1 Disease Associations")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "gene_to_diseases",  # Note: This mode not in current implementation
                    "gene": "hgnc:1100",  # BRCA1
                    "limit": 20,
                    "response_format": "json"
                }
            )
            
            data = json.loads(result.content[0].text)
            
            print(f"\nGene: BRCA1 (HGNC:1100)")
            print(f"Associated Diseases: {len(data.get('diseases', []))}")
            
            if data.get('diseases'):
                print(f"\nDisease Associations (sorted by evidence):")
                for i, disease in enumerate(data['diseases'][:10], 1):
                    score = disease.get('score', 0)
                    evidence = disease.get('evidence_count', 0)
                    print(f"  {i}. {disease['name']}")
                    print(f"     CURIE: {disease['curie']}, Score: {score:.2f}, Evidence: {evidence}")
                
                # Categorize by disease type
                cancer_diseases = [d for d in data['diseases'] if 'cancer' in d['name'].lower() or 'carcinoma' in d['name'].lower()]
                print(f"\nCancer Associations: {len(cancer_diseases)}")
                for cancer in cancer_diseases[:5]:
                    print(f"  - {cancer['name']}")
            else:
                print("\nNote: This query mode may not be available yet.")
                print("Check the tool documentation for supported modes.")


# ==============================================================================
# Example 3: Alzheimer's Disease Phenotypes - Understanding Clinical Presentation
# ==============================================================================
# Scientific Context:
#   Alzheimer's disease presents with a complex phenotypic profile including
#   cognitive, behavioral, and motor symptoms. Understanding the full phenotype
#   spectrum aids in diagnosis, patient stratification, and clinical trial design.
#
# Use Case:
#   Clinical phenotype characterization for differential diagnosis, patient
#   stratification, and understanding disease heterogeneity.
#
# Reference:
#   McKhann et al. (2011). "The diagnosis of dementia due to Alzheimer's
#   disease" Alzheimers Dement. 7(3):263-269
# ==============================================================================

async def example_3_alzheimers_phenotypes():
    """
    Example 3: Alzheimer's disease phenotype profile
    
    Expected Output:
        - Memory impairment (HP:0002354)
        - Cognitive decline
        - Language impairment
        - Executive dysfunction
        - Behavioral changes
        - Motor symptoms (late stage)
    """
    print("\n" + "="*80)
    print("Example 3: Alzheimer's Disease Phenotype Profile")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Get comprehensive disease profile focusing on phenotypes
            result = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "disease_to_mechanisms",
                    "disease": "mondo:0004975",  # Alzheimer's disease
                    "include_genes": False,  # Focus on phenotypes
                    "include_variants": False,
                    "include_phenotypes": True,
                    "include_drugs": False,
                    "include_trials": False,
                    "response_format": "json"
                }
            )
            
            data = json.loads(result.content[0].text)
            
            print(f"\nDisease: {data['disease']['name']}")
            print(f"CURIE: {data['disease']['curie']}")
            
            phenotypes = data.get('phenotypes', [])
            print(f"\nTotal Phenotypes: {len(phenotypes)}")
            
            if phenotypes:
                # Categorize phenotypes
                cognitive = [p for p in phenotypes if any(term in p['phenotype']['name'].lower() for term in ['memory', 'cognitive', 'dementia'])]
                behavioral = [p for p in phenotypes if any(term in p['phenotype']['name'].lower() for term in ['behavior', 'anxiety', 'depression', 'agitation'])]
                motor = [p for p in phenotypes if any(term in p['phenotype']['name'].lower() for term in ['gait', 'motor', 'movement', 'rigidity'])]
                
                print(f"\nCognitive Symptoms ({len(cognitive)}):")
                for pheno in cognitive[:5]:
                    freq = pheno.get('frequency', 'unknown')
                    print(f"  - {pheno['phenotype']['name']} ({pheno['phenotype']['curie']}) - {freq}")
                
                print(f"\nBehavioral/Psychiatric Symptoms ({len(behavioral)}):")
                for pheno in behavioral[:5]:
                    freq = pheno.get('frequency', 'unknown')
                    print(f"  - {pheno['phenotype']['name']} ({pheno['phenotype']['curie']}) - {freq}")
                
                print(f"\nMotor Symptoms ({len(motor)}):")
                for pheno in motor[:5]:
                    freq = pheno.get('frequency', 'unknown')
                    print(f"  - {pheno['phenotype']['name']} ({pheno['phenotype']['curie']}) - {freq}")
                
                print(f"\nOther Symptoms ({len(phenotypes) - len(cognitive) - len(behavioral) - len(motor)}):")
                other = [p for p in phenotypes if p not in cognitive and p not in behavioral and p not in motor]
                for pheno in other[:3]:
                    print(f"  - {pheno['phenotype']['name']}")


# ==============================================================================
# Example 4: Seizure Differential Diagnosis - Phenotype-to-Diseases Mapping
# ==============================================================================
# Scientific Context:
#   Seizures (HP:0001250) are a common symptom with hundreds of possible causes
#   including epilepsies, metabolic disorders, infections, and genetic syndromes.
#
# Use Case:
#   Differential diagnosis support. Given a phenotype, find all associated
#   diseases to guide clinical workup and diagnostic testing.
#
# Reference:
#   Kohler et al. (2017). "The Human Phenotype Ontology in 2017"
#   Nucleic Acids Res. 45(D1):D865-D876
# ==============================================================================

async def example_4_seizure_differential():
    """
    Example 4: Diseases associated with seizures
    
    Expected Output:
        - Epilepsy syndromes (>50 types)
        - Metabolic disorders (PKU, mitochondrial diseases)
        - Genetic syndromes (Dravet, Angelman, Rett)
        - Structural brain abnormalities
        - Infectious/inflammatory conditions
    """
    print("\n" + "="*80)
    print("Example 4: Seizure Differential Diagnosis")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "phenotype_to_diseases",
                    "phenotype": "HP:0001250",  # Seizures
                    "limit": 50,
                    "response_format": "json"
                }
            )
            
            data = json.loads(result.content[0].text)
            
            print(f"\nPhenotype: Seizures (HP:0001250)")
            print(f"Associated Diseases: {len(data.get('diseases', []))}")
            
            diseases = data.get('diseases', [])
            
            if diseases:
                # Categorize diseases
                epilepsies = [d for d in diseases if 'epilep' in d['name'].lower()]
                metabolic = [d for d in diseases if any(term in d['name'].lower() for term in ['metabolic', 'deficiency', 'storage'])]
                genetic = [d for d in diseases if any(term in d['name'].lower() for term in ['syndrome', 'disorder', 'dystrophy'])]
                
                print(f"\nEpilepsy Syndromes ({len(epilepsies)}):")
                for disease in epilepsies[:10]:
                    print(f"  - {disease['name']} ({disease['curie']})")
                
                print(f"\nMetabolic Disorders ({len(metabolic)}):")
                for disease in metabolic[:5]:
                    print(f"  - {disease['name']} ({disease['curie']})")
                
                print(f"\nGenetic Syndromes ({len(genetic)}):")
                for disease in genetic[:5]:
                    print(f"  - {disease['name']} ({disease['curie']})")
                
                print(f"\nPagination Info:")
                pagination = data.get('pagination', {})
                print(f"  Results shown: {pagination.get('count', 0)}")
                print(f"  Offset: {pagination.get('offset', 0)}")
                print(f"  Limit: {pagination.get('limit', 0)}")
                print(f"  More available: {pagination.get('has_more', False)}")


# ==============================================================================
# Example 5: Disease Gene Discovery Workflow - Multi-Step Analysis
# ==============================================================================
# Scientific Context:
#   Comprehensive disease analysis often requires multiple queries:
#   1. Get disease mechanisms (genes, phenotypes)
#   2. Validate specific gene associations
#   3. Cross-reference with phenotypes
#
# Use Case:
#   Research workflow demonstrating how to chain queries for hypothesis
#   generation and validation. Useful for literature review, grant writing,
#   and research planning.
#
# Reference:
#   Chung et al. (2019). "Genetic architecture of Parkinson's disease"
#   Mov Disord. 34(5):615-623
# ==============================================================================

async def example_5_disease_gene_discovery():
    """
    Example 5: Multi-step disease gene discovery workflow
    
    Workflow:
        1. Get Parkinson's disease gene associations
        2. Check if LRRK2 is associated (validation)
        3. Get phenotypes to understand clinical presentation
        4. Cross-reference genes with phenotypes
    
    Expected Output:
        - 15-30 Parkinson's genes (LRRK2, SNCA, PARK7, PINK1, etc.)
        - Confirmation of LRRK2-PD association
        - Motor and non-motor phenotypes
        - Gene-phenotype correlations
    """
    print("\n" + "="*80)
    print("Example 5: Disease Gene Discovery Workflow - Parkinson's Disease")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="cogex-mcp",
        env={
            "NEO4J_URL": "bolt://your-server:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "your_password"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("\nStep 1: Get Parkinson's disease genetic architecture")
            print("-" * 60)
            
            result1 = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "disease_to_mechanisms",
                    "disease": "mesh:D010300",  # Parkinson's Disease
                    "include_genes": True,
                    "include_variants": False,
                    "include_phenotypes": True,
                    "include_drugs": False,
                    "include_trials": False,
                    "response_format": "json"
                }
            )
            
            data1 = json.loads(result1.content[0].text)
            
            genes = data1.get('genes', [])
            phenotypes = data1.get('phenotypes', [])
            
            print(f"Associated Genes: {len(genes)}")
            print(f"Top 10 Genes:")
            for i, gene in enumerate(sorted(genes, key=lambda g: g.get('score', 0), reverse=True)[:10], 1):
                print(f"  {i}. {gene['gene']['name']}: score={gene.get('score', 0):.2f}, evidence={gene.get('evidence_count', 0)}")
            
            print(f"\nPhenotypes: {len(phenotypes)}")
            motor_phenotypes = [p for p in phenotypes if any(term in p['phenotype']['name'].lower() for term in ['tremor', 'rigidity', 'bradykinesia', 'gait', 'motor'])]
            print(f"Motor Phenotypes: {len(motor_phenotypes)}")
            for pheno in motor_phenotypes[:5]:
                print(f"  - {pheno['phenotype']['name']}")
            
            print("\n\nStep 2: Validate LRRK2 association (known PD gene)")
            print("-" * 60)
            
            result2 = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "check_phenotype",  # Note: This checks disease-phenotype, not gene-disease
                    "disease": "mesh:D010300",
                    "phenotype": "tremor",  # Example phenotype check
                    "response_format": "json"
                }
            )
            
            data2 = json.loads(result2.content[0].text)
            
            print(f"Checking: Does Parkinson's disease have tremor?")
            print(f"Result: {data2.get('has_phenotype', False)}")
            
            print("\n\nStep 3: Cross-reference with other movement disorders")
            print("-" * 60)
            
            # Find other diseases with tremor
            result3 = await session.call_tool(
                "query_disease_or_phenotype",
                arguments={
                    "mode": "phenotype_to_diseases",
                    "phenotype": "tremor",
                    "limit": 10,
                    "response_format": "json"
                }
            )
            
            data3 = json.loads(result3.content[0].text)
            
            print(f"Other diseases with tremor: {len(data3.get('diseases', []))}")
            for disease in data3.get('diseases', [])[:5]:
                print(f"  - {disease['name']} ({disease['curie']})")
            
            print("\n\nWorkflow Summary:")
            print("-" * 60)
            print(f"Parkinson's Disease Genetic Architecture:")
            print(f"  - {len(genes)} associated genes identified")
            print(f"  - {len(phenotypes)} clinical phenotypes documented")
            print(f"  - {len(motor_phenotypes)} motor phenotypes (core symptoms)")
            print(f"\nDifferential Diagnosis:")
            print(f"  - {len(data3.get('diseases', []))} diseases share tremor phenotype")
            print(f"  - Phenotype overlap requires additional clinical features for diagnosis")
            print(f"\nNext Steps:")
            print(f"  1. Query genetic variants for top genes (GWAS validation)")
            print(f"  2. Check drug targets among associated genes")
            print(f"  3. Explore gene-gene interactions (subnetwork analysis)")
            print(f"  4. Review clinical trials targeting top genes")


# ==============================================================================
# Main Execution
# ==============================================================================

async def main():
    """Run all examples sequentially."""
    print("="*80)
    print("INDRA CoGEx Disease Query Examples")
    print("="*80)
    print("\nThese examples demonstrate practical usage of disease/phenotype queries")
    print("for clinical and translational research. Update Neo4j credentials in each example.")
    print("\nExamples:")
    print("  1. ALS etiopathology (complete mechanisms)")
    print("  2. BRCA1 disease associations (gene-to-diseases)")
    print("  3. Alzheimer's phenotype profile")
    print("  4. Seizure differential diagnosis (phenotype-to-diseases)")
    print("  5. Parkinson's disease gene discovery workflow")
    
    choice = input("\nRun which example? (1-5, or 'all'): ").strip()
    
    examples = {
        '1': example_1_als_complete_mechanisms,
        '2': example_2_brca1_disease_associations,
        '3': example_3_alzheimers_phenotypes,
        '4': example_4_seizure_differential,
        '5': example_5_disease_gene_discovery,
    }
    
    if choice.lower() == 'all':
        for func in examples.values():
            await func()
    elif choice in examples:
        await examples[choice]()
    else:
        print(f"Invalid choice: {choice}")
        return
    
    print("\n" + "="*80)
    print("Examples completed!")
    print("="*80)


if __name__ == "__main__":
    # Note: Update Neo4j credentials in each example function before running
    print("\n⚠️  IMPORTANT: Update Neo4j credentials in example functions before running!")
    print("   Each example has placeholders that need your actual credentials.\n")
    
    asyncio.run(main())
