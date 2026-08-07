def get_css():
    return """
    <style>
    /* Fundo da barra lateral mais moderno */
    [data-testid="stSidebar"] {
        background-color: #f1f3f5;
        border-right: 1px solid #e9ecef;
    }
    
    /* Botões com cor forte, modernos e arredondados */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 48px;
        font-weight: 600;
        background-color: #0d6efd !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 6px rgba(13, 110, 253, 0.2);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #0b5ed7 !important;
        box-shadow: 0 6px 8px rgba(13, 110, 253, 0.3);
    }
    
    /* Campos de texto arredondados */
    input {
        border-radius: 8px !important;
    }
    </style>
    """
