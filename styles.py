def get_css():
    return """
    <style>
    /* Estilo Geral da Sidebar */
    .stSidebar {
        background-color: #f8f9fa;
    }
    
    /* Botões Modernos com Destaque e Efeito Hover */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 45px;
        font-weight: 600;
        background-color: #1f77b4;
        color: white;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #135d8a;
        color: #ffffff;
    }
    
    /* Campos de Entrada Estilizados */
    .stTextInput>div>div>input {
        border-radius: 8px;
        border: 1px solid #ced4da;
        padding: 10px;
    }
    </style>
    """
