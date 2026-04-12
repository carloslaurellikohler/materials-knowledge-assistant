"""
chunker.py
----------
Estratégias de chunking para o pipeline de ingestão de PDFs.

Implementa duas estratégias (Task 1.5.1 — AIP-C01):
  - Fixed-size chunking:    divide por número de tokens com overlap
  - Hierarchical chunking:  respeita estrutura do documento (seções, parágrafos)

Sem dependências AWS — totalmente testável localmente.
"""

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Configurações padrão ────────────────────────────────────────────────────

FIXED_CHUNK_SIZE    = 512   # tokens aproximados por chunk
FIXED_CHUNK_OVERLAP = 64    # tokens de overlap entre chunks consecutivos
WORDS_PER_TOKEN     = 0.75  # aproximação: 1 token ≈ 0.75 palavras em PT-BR


class ChunkType(str, Enum):
    FIXED        = "fixed"
    HIERARCHICAL = "hierarchical"


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class DocumentMetadata:
    """Metadados extraídos do PDF — preenchidos pelo pdf_processor.py."""
    document_id: str
    book_title:  str
    author:      str       = "Desconhecido"
    chapter:     str       = ""
    page_number: int       = 0


@dataclass
class Chunk:
    """Unidade de texto que será embedada e indexada no OpenSearch."""
    chunk_id:    str
    document_id: str
    content:     str
    chunk_index: int
    chunk_type:  ChunkType
    metadata:    DocumentMetadata
    token_count: int        = 0
    extra:       dict       = field(default_factory=dict)

    def to_opensearch_doc(self) -> dict:
        """Serializa para o formato esperado pelo índice materials-chunks."""
        return {
            "chunk_id":    self.chunk_id,
            "document_id": self.document_id,
            "content":     self.content,
            "metadata": {
                "book_title":  self.metadata.book_title,
                "author":      self.metadata.author,
                "chapter":     self.metadata.chapter,
                "page_number": self.metadata.page_number,
                "chunk_index": self.chunk_index,
                "chunk_type":  self.chunk_type.value,
            },
            # embedding será adicionado pelo embedder.py
        }

    def to_dynamodb_item(self) -> dict:
        """Serializa para a tabela materials-kb-chunks no DynamoDB."""
        return {
            "document_id": self.document_id,
            "chunk_id":    self.chunk_id,
            "book_title":  self.metadata.book_title,
            "author":      self.metadata.author,
            "chapter":     self.metadata.chapter,
            "page_number": self.metadata.page_number,
            "chunk_index": self.chunk_index,
            "chunk_type":  self.chunk_type.value,
            "token_count": self.token_count,
            "content_preview": self.content[:200],  # preview para debug
        }


# ── Utilitários ──────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """
    Estimativa simples de tokens baseada em contagem de palavras.
    Suficiente para chunking — não precisa de tokenizer exato aqui.
    Titan Embeddings v2 suporta até 8192 tokens de input.
    """
    words = len(text.split())
    return int(words / WORDS_PER_TOKEN)


def generate_chunk_id(document_id: str, chunk_index: int) -> str:
    """ID determinístico para permitir re-ingestão idempotente."""
    return f"{document_id}#chunk#{chunk_index:04d}"


def clean_text(text: str) -> str:
    """
    Limpeza básica do texto extraído pelo Textract.
    Remove artefatos comuns de OCR em PDFs técnicos.
    """
    # Remove múltiplas quebras de linha
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove espaços múltiplos
    text = re.sub(r' {2,}', ' ', text)
    # Remove hifenização de quebra de linha (ex: "mate-\nrial" → "material")
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    # Remove cabeçalhos/rodapés numéricos isolados (números de página)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


# ── Estratégia 1: Fixed-size Chunking ────────────────────────────────────────

def fixed_size_chunking(
    text:           str,
    metadata:       DocumentMetadata,
    chunk_size:     int = FIXED_CHUNK_SIZE,
    chunk_overlap:  int = FIXED_CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Divide o texto em chunks de tamanho fixo (em palavras) com overlap.

    Por que overlap?
    Garante que conceitos que aparecem na fronteira entre dois chunks
    não sejam perdidos em nenhum deles. Fundamental para textos técnicos
    onde uma definição pode começar no fim de um parágrafo e continuar
    no próximo.

    Args:
        text:          Texto limpo extraído do PDF
        metadata:      Metadados do documento
        chunk_size:    Tamanho alvo em tokens (aprox.)
        chunk_overlap: Tokens de overlap entre chunks consecutivos

    Returns:
        Lista de Chunk ordenada por chunk_index
    """
    text   = clean_text(text)
    words  = text.split()
    chunks = []

    # Converte tokens → palavras para o loop
    size_words    = int(chunk_size    * WORDS_PER_TOKEN)
    overlap_words = int(chunk_overlap * WORDS_PER_TOKEN)
    step          = size_words - overlap_words

    if step <= 0:
        raise ValueError(
            f"overlap ({chunk_overlap}) deve ser menor que chunk_size ({chunk_size})"
        )

    start       = 0
    chunk_index = 0

    while start < len(words):
        end        = min(start + size_words, len(words))
        chunk_text = " ".join(words[start:end])

        if len(chunk_text.strip()) < 50:
            # Ignora chunks muito pequenos (geralmente artefatos de OCR)
            break

        chunks.append(Chunk(
            chunk_id    = generate_chunk_id(metadata.document_id, chunk_index),
            document_id = metadata.document_id,
            content     = chunk_text,
            chunk_index = chunk_index,
            chunk_type  = ChunkType.FIXED,
            metadata    = metadata,
            token_count = estimate_tokens(chunk_text),
        ))

        chunk_index += 1
        start       += step

    return chunks


# ── Estratégia 2: Hierarchical Chunking ──────────────────────────────────────

# Padrões para detectar títulos de seção em textos técnicos de eng. materiais
#
# Por que simplificamos o regex?
# O Python re com IGNORECASE não expande acentos de forma confiável dentro
# de character classes ([A-Z] não captura Á, É, etc. mesmo com flag).
# A solução é usar \w e validar o tamanho da linha — mais robusto para
# textos em PT-BR extraídos por OCR.
SECTION_PATTERNS = [
    # "1. Introdução", "2.3 Microestrutura", "4.2.1 Ensaio de Tração"
    # Número(s) seguido de ponto e texto de 3–80 chars
    r'^\s*\d+(?:\.\d+)*[\.\s]\s*\w.{2,78}$',
    # "INTRODUÇÃO", "MICROESTRUTURA E PROPRIEDADES" — linha toda maiúscula
    r'^\s*[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ\s]{4,60}$',
    # "Capítulo 3", "Seção 2.4", "Chapter 3"
    r'^\s*(?:Capítulo|Seção|Parte|Chapter|Section)\s+[\d\.]+',
]

SECTION_REGEX = re.compile(
    '|'.join(SECTION_PATTERNS),
    re.MULTILINE
)


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Divide o texto em seções baseado em padrões de título.

    Returns:
        Lista de tuplas (título_da_seção, conteúdo_da_seção)
    """
    lines    = text.split('\n')
    sections = []
    current_title   = "Introdução"
    current_content = []

    for line in lines:
        if SECTION_REGEX.match(line) and len(line.strip()) > 3:
            # Salva seção anterior se tiver conteúdo
            if current_content:
                content = '\n'.join(current_content).strip()
                if content:
                    sections.append((current_title, content))
            # Inicia nova seção
            current_title   = line.strip()
            current_content = []
        else:
            current_content.append(line)

    # Salva última seção
    if current_content:
        content = '\n'.join(current_content).strip()
        if content:
            sections.append((current_title, content))

    # Fallback: se nenhuma seção detectada, trata texto todo como uma seção
    if not sections:
        sections = [("Conteúdo", text)]

    return sections


def _split_section_into_paragraphs(
    section_title:   str,
    section_content: str,
    metadata:        DocumentMetadata,
    start_index:     int,
    max_tokens:      int = FIXED_CHUNK_SIZE,
) -> list[Chunk]:
    """
    Divide uma seção em chunks respeitando parágrafos.
    Se um parágrafo for maior que max_tokens, aplica fixed-size como fallback.
    """
    paragraphs  = re.split(r'\n\n+', section_content)
    chunks      = []
    buffer      = []
    buffer_tokens = 0
    chunk_index = start_index

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        para_tokens = estimate_tokens(paragraph)

        # Parágrafo sozinho já excede o limite → aplica fixed-size
        if para_tokens > max_tokens:
            # Flush do buffer atual primeiro
            if buffer:
                content = '\n\n'.join(buffer)
                chunks.append(Chunk(
                    chunk_id    = generate_chunk_id(metadata.document_id, chunk_index),
                    document_id = metadata.document_id,
                    content     = content,
                    chunk_index = chunk_index,
                    chunk_type  = ChunkType.HIERARCHICAL,
                    metadata    = metadata,
                    token_count = estimate_tokens(content),
                    extra       = {"section": section_title},
                ))
                chunk_index += 1
                buffer        = []
                buffer_tokens = 0

            # Fixed-size fallback para o parágrafo longo
            sub_meta = DocumentMetadata(
                document_id = metadata.document_id,
                book_title  = metadata.book_title,
                author      = metadata.author,
                chapter     = section_title,
                page_number = metadata.page_number,
            )
            sub_chunks = fixed_size_chunking(paragraph, sub_meta)
            for sc in sub_chunks:
                sc.chunk_index = chunk_index
                sc.chunk_id    = generate_chunk_id(metadata.document_id, chunk_index)
                sc.chunk_type  = ChunkType.HIERARCHICAL
                sc.extra       = {"section": section_title, "overflow": True}
                chunks.append(sc)
                chunk_index += 1
            continue

        # Adiciona parágrafo ao buffer se couber
        if buffer_tokens + para_tokens <= max_tokens:
            buffer.append(paragraph)
            buffer_tokens += para_tokens
        else:
            # Flush do buffer e inicia novo
            if buffer:
                content = '\n\n'.join(buffer)
                chunks.append(Chunk(
                    chunk_id    = generate_chunk_id(metadata.document_id, chunk_index),
                    document_id = metadata.document_id,
                    content     = content,
                    chunk_index = chunk_index,
                    chunk_type  = ChunkType.HIERARCHICAL,
                    metadata    = metadata,
                    token_count = estimate_tokens(content),
                    extra       = {"section": section_title},
                ))
                chunk_index += 1

            buffer        = [paragraph]
            buffer_tokens = para_tokens

    # Flush final
    if buffer:
        content = '\n\n'.join(buffer)
        chunks.append(Chunk(
            chunk_id    = generate_chunk_id(metadata.document_id, chunk_index),
            document_id = metadata.document_id,
            content     = content,
            chunk_index = chunk_index,
            chunk_type  = ChunkType.HIERARCHICAL,
            metadata    = metadata,
            token_count = estimate_tokens(content),
            extra       = {"section": section_title},
        ))

    return chunks


def hierarchical_chunking(
    text:       str,
    metadata:   DocumentMetadata,
    max_tokens: int = FIXED_CHUNK_SIZE,
) -> list[Chunk]:
    """
    Divide o texto respeitando a hierarquia do documento:
    Documento → Seções → Parágrafos → Chunks

    Por que hierarchical para textos técnicos?
    Em livros de Engenharia de Materiais, cada seção trata de um tema
    específico (ex: "Diagrama Fe-C", "Ensaio Charpy"). Manter chunks
    dentro da mesma seção garante que o contexto recuperado pelo RAG
    seja semanticamente coerente — a resposta não vai misturar conteúdo
    de seções diferentes no mesmo chunk.

    Args:
        text:       Texto limpo extraído do PDF
        metadata:   Metadados do documento
        max_tokens: Tamanho máximo de cada chunk em tokens

    Returns:
        Lista de Chunk ordenada por chunk_index
    """
    text     = clean_text(text)
    sections = _split_into_sections(text)
    all_chunks  = []
    chunk_index = 0

    for section_title, section_content in sections:
        # Atualiza chapter no metadata para esta seção
        section_metadata = DocumentMetadata(
            document_id = metadata.document_id,
            book_title  = metadata.book_title,
            author      = metadata.author,
            chapter     = section_title,
            page_number = metadata.page_number,
        )

        section_chunks = _split_section_into_paragraphs(
            section_title   = section_title,
            section_content = section_content,
            metadata        = section_metadata,
            start_index     = chunk_index,
            max_tokens      = max_tokens,
        )

        all_chunks.extend(section_chunks)
        chunk_index += len(section_chunks)

    return all_chunks


# ── Interface principal ───────────────────────────────────────────────────────

def chunk_document(
    text:      str,
    metadata:  DocumentMetadata,
    strategy:  ChunkType = ChunkType.HIERARCHICAL,
) -> list[Chunk]:
    """
    Ponto de entrada principal do chunker.

    Estratégia recomendada:
    - HIERARCHICAL: textos com estrutura clara (livros, artigos técnicos)
    - FIXED:        textos sem estrutura (OCR de má qualidade, tabelas brutas)

    O pdf_processor.py tenta HIERARCHICAL primeiro. Se produzir menos de
    3 chunks (texto sem estrutura detectável), cai para FIXED automaticamente.
    """
    if strategy == ChunkType.HIERARCHICAL:
        chunks = hierarchical_chunking(text, metadata)

        # Fallback para fixed se hierárquico não detectou estrutura
        if len(chunks) < 3:
            chunks = fixed_size_chunking(text, metadata)

        return chunks

    return fixed_size_chunking(text, metadata)


# ── Testes locais ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Execute localmente para validar o chunker sem precisar de AWS:
        python chunker.py
    """
    sample_text = """
1. Introdução à Metalurgia

A metalurgia é a ciência que estuda os metais e suas ligas, abrangendo desde
a extração dos minérios até a fabricação de produtos finais com propriedades
mecânicas específicas.

Os metais possuem estrutura cristalina que determina suas propriedades.
A estrutura cristalina mais comum nos aços é a cúbica de corpo centrado (CCC)
na fase ferrita e cúbica de face centrada (CFC) na fase austenita.

2. Diagrama de Fases Fe-C

O diagrama de fases ferro-carbono é fundamental para compreender as
transformações microestruturais que ocorrem durante o tratamento térmico
dos aços.

O ponto eutetóide ocorre a 727°C com 0,76% de carbono, onde a austenita
se transforma em perlita (mistura de ferrita e cementita).

2.1 Transformações no Estado Sólido

As transformações no estado sólido incluem a transformação martensítica,
bainítica e perlítica, cada uma com características microestruturais
e propriedades mecânicas distintas.

A martensita é formada por resfriamento rápido (têmpera) e possui
estrutura tetragonal de corpo centrado (TCC), sendo a microestrutura
mais dura dos aços carbono.
    """

    meta = DocumentMetadata(
        document_id = "doc-001",
        book_title  = "Ciência dos Materiais — Callister",
        author      = "William D. Callister Jr.",
        chapter     = "",
        page_number = 1,
    )

    print("=" * 60)
    print("TESTE 1: Hierarchical Chunking")
    print("=" * 60)
    chunks = chunk_document(sample_text, meta, ChunkType.HIERARCHICAL)
    for c in chunks:
        print(f"\n[Chunk {c.chunk_index}] section={c.extra.get('section','')}")
        print(f"  tokens : {c.token_count}")
        print(f"  preview: {c.content[:120]}...")

    print("\n" + "=" * 60)
    print("TESTE 2: Fixed-size Chunking")
    print("=" * 60)
    chunks_fixed = chunk_document(sample_text, meta, ChunkType.FIXED)
    for c in chunks_fixed:
        print(f"\n[Chunk {c.chunk_index}] tokens={c.token_count}")
        print(f"  preview: {c.content[:120]}...")

    print("\n" + "=" * 60)
    print(f"Hierarchical: {len(chunks)} chunks")
    print(f"Fixed-size:   {len(chunks_fixed)} chunks")
    print("=" * 60)

    print("\nOpenSearch doc sample:")
    import json
    print(json.dumps(chunks[0].to_opensearch_doc(), indent=2, ensure_ascii=False))
