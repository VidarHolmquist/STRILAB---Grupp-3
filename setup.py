from setuptools import setup, find_packages

setup(
    name="local_hybrid_rag",
    version="0.1.0",
    description="A local, private hybrid RAG retriever using ChromaDB and E5 Multilingual",
    author="Your Name",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "chromadb>=0.5.0",
        "snowballstemmer>=2.2.0",
        "sentence-transformers>=3.0.0",
        "rank-bm25>=0.2.2",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
