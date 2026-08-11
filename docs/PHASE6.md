  Phase 6 — OWL Learning Recommendation Engine telah selesai 100% dengan 46 passed unit & integration tests (termasuk regression test Phase 1–5 dan performance benchmarks).                                     
  ──────                                                                                                                                                                                                         
  ## 🏛️ 1. Architecture Summary                                                                                                                                                                                  
                                                                                                                                                                                                                 
  Sesuai spesifikasi arsitektur Phase 6, Qwen tidak dijadikan mesin ranking utama. Scoring dan ranking berjalan 100% deterministic di FastAPI, sedangkan Qwen 0.5B bertugas memberikan natural language          
  explanation singkat atas hasil rekomendasi.                                                                                                                                                                    
                                                                                                                                                                                                                 
                   Laravel OWL LMS                                                                                                                                                                               
                         │                                                                                                                                                                                       
                         │ User Profile, History & Candidates                                                                                                                                                    
                         ▼                                                                                                                                                                                       
               ┌──────────────────┐                                                                                                                                                                              
               │   AI Service     │                                                                                                                                                                              
               │  Recommendation  │                                                                                                                                                                              
               └─────────┬────────┘                                                                                                                                                                              
                         │                                                                                                                                                                                       
            ┌────────────┼────────────┐                                                                                                                                                                          
            ▼            ▼            ▼                                                                                                                                                                          
         Division     Position     Learning                                                                                                                                                                      
                                    History                                                                                                                                                                      
            │            │            │                                                                                                                                                                          
            └────────────┼────────────┘                                                                                                                                                                          
                         ▼                                                                                                                                                                                       
                 Candidate Filter                                                                                                                                                                                
                & Exclusions                                                                                                                                                                                     
                         │                                                                                                                                                                                       
                         ▼                                                                                                                                                                                       
                Deterministic Scoring                                                                                                                                                                            
                 (30/25/20/15/10)                                                                                                                                                                                
                         │                                                                                                                                                                                       
                         ▼                                                                                                                                                                                       
                Recommendation Ranking                                                                                                                                                                           
                         │                                                                                                                                                                                       
                         ▼                                                                                                                                                                                       
                Qwen 0.5B GGUF                                                                                                                                                                                   
                 (LLM Explanation)                                                                                                                                                                               
                         │                                                                                                                                                                                       
                         ▼                                                                                                                                                                                       
                   Laravel OWL                                                                                                                                                                                   
  ──────                                                                                                                                                                                                         
  ## 🔍 2. Audit Findings — Real Laravel OWL Schema                                                                                                                                                              
                                                                                                                                                                                                                 
  Hasil audit pada codebase Laravel OWL (/home/memoriesendx/Documents/POSKO/owl-feat-dafa (Copy 3)) mengonfirmasi field dan struktur relasi nyata sebagai berikut:                                               
                                                                                                                                                                                                                 
  • User (users table):                                                                                                                                                                                          
      • Fields: id, name, email, division, department (dipakai sebagai position/role), team, id_org_unit, role, active.                                                                                          
      • Relasi: contentUsers(), assesmentResults().                                                                                                                                                              
  • Content (content table):                                                                                                                                                                                     
      • Fields: id, title, type, classification_id, description, exam (OK/NOT), active (Active/Inactive), has_deadline, from_date, to_date, learning_hours, views.                                               
      • Relasi: classification(), contentuser(), trainingPlans().                                                                                                                                                
  • TrainingPlan (Playlist - trainingplan table):                                                                                                                                                                
      • Fields: id, title, slug, active (Active/Inactive), has_deadline, from_date, to_date, total_duration_seconds, learning_hours.                                                                             
      • Relasi: trainingplandetail() (pivot ke content).                                                                                                                                                         
  • ContentUser (content_users table):                                                                                                                                                                           
      • Fields: id, user_id, content_id, progress (0–100), status (optional/mandatory), finish (0/1), learning_status.                                                                                           
  • Assesment & AssesmentResult (assesment_results table):                                                                                                                                                       
      • Fields: id, user_id, assesment_id, score (0–100), final.                                                                                                                                                 
  • Classification (classification table):                                                                                                                                                                       
      • Fields: id, classification_name, slug.                                                                                                                                                                   
                                                                                                                                                                                                                 
  ──────                                                                                                                                                                                                         
  ## 🧮 3. Deterministic Scoring Formula & Configuration                                                                                                                                                         
                                                                                                                                                                                                                 
  Formula scoring disimpan dalam konfigurasi yang dapat disesuaikan di .env:                                                                                                                                     
                                                                                                                                                                                                                 
    Score = min ⎛100,W    + W    + W    + W    + W   ⎞                                                                                                                                                           
                ⎝     div    pos    gap    ass    rel⎠                                                                                                                                                           
                                                                                                                                                                                                                 
    # Recommendation Engine Configurable Weights                                                                                                                                                                 
    RECOMMENDATION_WEIGHT_DIVISION=30.0                                                                                                                                                                          
    RECOMMENDATION_WEIGHT_POSITION=25.0                                                                                                                                                                          
    RECOMMENDATION_WEIGHT_GAP=20.0                                                                                                                                                                               
    RECOMMENDATION_WEIGHT_ASSESSMENT=15.0                                                                                                                                                                        
    RECOMMENDATION_WEIGHT_RELEVANCE=10.0                                                                                                                                                                         
    RECOMMENDATION_DEFAULT_LIMIT=5                                                                                                                                                                               
    RECOMMENDATION_MAX_LIMIT=50                                                                                                                                                                                  
                                                                                                                                                                                                                 
  ### 📋 Break Down Aturan Scoring:                                                                                                                                                                              
                                                                                                                                                                                                                 
  1. **Division Match (                                                                                                                                                                                          
                                                                                                                                                                                                                 
    W    = 30                                                                                                                                                                                                    
     div                                                                                                                                                                                                         
                                                                                                                                                                                                                 
  )**: Match langsung target divisi kandidat dengan divisi user (+30), atau kemunculan divisi pada judul/deskripsi (+21).                                                                                        
  2. **Position Match (                                                                                                                                                                                          
                                                                                                                                                                                                                 
    W    = 25                                                                                                                                                                                                    
     pos                                                                                                                                                                                                         
                                                                                                                                                                                                                 
  )**: Match langsung posisi/department kandidat dengan role user (+25), atau match skop role (+15).                                                                                                             
  3. **Learning Gap (                                                                                                                                                                                            
                                                                                                                                                                                                                 
    W    = 20                                                                                                                                                                                                    
     gap                                                                                                                                                                                                         
                                                                                                                                                                                                                 
  )**: Evaluasi jika user telah menyelesaikan modul dasar pada suatu kategori (misal Safety Induction) dan kandidat merupakan modul tingkatan berikutnya pada kategori tersebut (+20).                           
  4. **Assessment Weakness Signal (                                                                                                                                                                              
                                                                                                                                                                                                                 
    W    = 15                                                                                                                                                                                                    
     ass                                                                                                                                                                                                         
                                                                                                                                                                                                                 
  )**: Jika nilai assessment user di bawah threshold (<70), sistem memberikan dorongan rekomendasi modul penguatan pada topik tersebut (+15).                                                                    
  5. **Relevance Baseline (                                                                                                                                                                                      
                                                                                                                                                                                                                 
    W    = 10                                                                                                                                                                                                    
     rel                                                                                                                                                                                                         
                                                                                                                                                                                                                 
  )**: Relevance kategori dasar modul aktif.                                                                                                                                                                     
  6. Hard Filter & Exclusions:                                                                                                                                                                                   
                                                                                                                                                                                                                 
  • Konten/Playlist yang sudah selesai (finish = 1 atau progress = 100) otomatis di-exclude.                                                                                                                     
  • Konten dengan active = Inactive atau deadline sudah lewat (to_date < today) otomatis di-exclude.                                                                                                             
  ──────                                                                                                                                                                                                         
  ## 🌐 4. Recommendation API Endpoint                                                                                                                                                                           
                                                                                                                                                                                                                 
  ### POST /api/v1/recommendations                                                                                                                                                                               
                                                                                                                                                                                                                 
  #### Example Request Body (dari Laravel):                                                                                                                                                                      
                                                                                                                                                                                                                 
    {                                                                                                                                                                                                            
        "application": "owl",                                                                                                                                                                                    
        "user": {                                                                                                                                                                                                
            "id": 123,                                                                                                                                                                                           
            "name": "Budi Santoso",                                                                                                                                                                              
            "division": "Production",                                                                                                                                                                            
            "position": "Supervisor",                                                                                                                                                                            
            "department": "Safety"                                                                                                                                                                               
        },                                                                                                                                                                                                       
        "completed_content": [101],                                                                                                                                                                              
        "completed_playlists": [],                                                                                                                                                                               
        "in_progress_content": [{"id": 105, "progress": 30}],                                                                                                                                                    
        "assessment_results": [                                                                                                                                                                                  
            {"assessment_id": 1, "title": "Safety Exam", "score": 55.0}                                                                                                                                          
        ],                                                                                                                                                                                                       
        "candidates": [                                                                                                                                                                                          
            {                                                                                                                                                                                                    
                "id": 102,                                                                                                                                                                                       
                "type": "content",                                                                                                                                                                               
                "title": "Advanced Safety Management",                                                                                                                                                           
                "description": "Safety management for production supervisors",                                                                                                                                   
                "classification_name": "Safety",                                                                                                                                                                 
                "target_division": "Production",                                                                                                                                                                 
                "target_position": "Supervisor",                                                                                                                                                                 
                "active": "Active"                                                                                                                                                                               
            },                                                                                                                                                                                                   
            {                                                                                                                                                                                                    
                "id": 103,                                                                                                                                                                                       
                "type": "playlist",                                                                                                                                                                              
                "title": "Production Leadership Playlist",                                                                                                                                                       
                "classification_name": "Safety",                                                                                                                                                                 
                "target_division": "Production",                                                                                                                                                                 
                "target_position": "Supervisor",                                                                                                                                                                 
                "active": "Active"                                                                                                                                                                               
            }                                                                                                                                                                                                    
        ],                                                                                                                                                                                                       
        "limit": 5                                                                                                                                                                                               
    }                                                                                                                                                                                                            
                                                                                                                                                                                                                 
  #### Example Response Output:                                                                                                                                                                                  
                                                                                                                                                                                                                 
    {                                                                                                                                                                                                            
        "application": "owl",                                                                                                                                                                                    
        "user_id": 123,                                                                                                                                                                                          
        "recommendations": [                                                                                                                                                                                     
            {                                                                                                                                                                                                    
                "type": "content",                                                                                                                                                                               
                "id": 102,                                                                                                                                                                                       
                "title": "Advanced Safety Management",                                                                                                                                                           
                "slug": null,                                                                                                                                                                                    
                "classification_name": "Safety",                                                                                                                                                                 
                "score": 100,                                                                                                                                                                                    
                "reasons": [                                                                                                                                                                                     
                    "Matches user division (Production)",                                                                                                                                                        
                    "Matches user position (Supervisor)",                                                                                                                                                        
                    "Addresses learning gap following completed Safety",                                                                                                                                         
                    "Recommended for reinforcement based on assessment score (55.0)"                                                                                                                             
                ],                                                                                                                                                                                               
                "score_breakdown": {                                                                                                                                                                             
                    "division": 30.0,                                                                                                                                                                            
                    "position": 25.0,                                                                                                                                                                            
                    "learning_gap": 20.0,                                                                                                                                                                        
                    "assessment": 15.0,                                                                                                                                                                          
                    "relevance": 10.0                                                                                                                                                                            
                }                                                                                                                                                                                                
            }                                                                                                                                                                                                    
        ],                                                                                                                                                                                                       
        "explanation": "Materi 'Advanced Safety Management' sangat direkomendasikan untuk mendukung peran Anda sebagai Supervisor di divisi Production dan memperdalam pemahaman safety setelah hasil evaluasi   
  sebelumnya.",                                                                                                                                                                                                  
        "explanation_status": "success",                                                                                                                                                                         
        "generated_at": "2026-08-11T20:07:03.611000+00:00"                                                                                                                                                       
    }                                                                                                                                                                                                            
                                                                                                                                                                                                                 
  │ ⚠️ Ketahanan Failure (Fault Tolerance): Jika container llama-server / Qwen sedang down atau offline, API tetap berhasil mengembalikan hasil ranking rekomendasi dengan explanation: null dan                 
  │ explanation_status: "unavailable".                                                                                                                                                                           
  ──────                                                                                                                                                                                                         
  ## 📊 5. Benchmark Performance Results                                                                                                                                                                         
                                                                                                                                                                                                                 
  Uji performa kandidat pada skala 10, 50, 100, dan 500 kandidat dilakukan via tests/test_recommendation_benchmark.py:                                                                                           
                                                                                                                                                                                                                 
   Candidate Scale                                                     │ Candidate Generation & Scoring Latency                             │ Result Status
  ─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────
   10 Candidates                                                       │ 0.214 ms                                                           │ ✅ PASSED
   50 Candidates                                                       │ 1.030 ms                                                           │ ✅ PASSED
   100 Candidates                                                      │ 1.816 ms                                                           │ ✅ PASSED
   500 Candidates                                                      │ 8.849 ms                                                           │ ✅ PASSED
  
  Engine ranking tanpa Qwen berjalan sangat cepat (<9  ms untuk 500 kandidat) dan tidak membebankan CPU/RAM.
  ──────
  ## 🧪 6. Test Results Summary
  
    ================================================================
    Phase 1: Foundation & Docker Base                 : PASSED
    Phase 2: LLM Service & Qwen 0.5B Integration      : PASSED
    Phase 3: Vector DB & Qdrant Setup                 : PASSED
    Phase 4: Document PDF RAG                         : PASSED
    Phase 5: Video & Audio Transcription (Whisper)    : PASSED
    Phase 6: OWL Learning Recommendation Engine       : PASSED
    ================================================================
    TOTAL REGRESSION & PHASE 6 SUITE                  : 46 PASSED
    ================================================================
  ──────
  ## 🐳 7. Tetap 3 Container AI
  
  Komposisi container deployment tetap efisien:
  
    ai-service
     ├── FastAPI Gateway
     ├── PDF RAG
     ├── Video RAG
     ├── Whisper STT
     ├── FFmpeg
     └── OWL Recommendation Engine
  
    llama-server
     └── Qwen2.5 0.5B GGUF
  
    qdrant
     └── Vector DB
  ──────
  ### ⏭️ NEXT STEP
  
  PHASE 7 — MCP / LMS TOOLS (integrasi tool-calling terkontrol FastAPI & Qwen).

──────────────────────────────────────────────────────────────────────────────────