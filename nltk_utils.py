import nltk
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.stem.snowball import SnowballStemmer
from nltk.corpus import stopwords

nltk.download('stopwords')
nltk.download('punkt')

english_stemmer = SnowballStemmer('english')


def stem_tokenizar(text):
    tokens = word_tokenize(text)
    stemmed_tokens = [english_stemmer.stem(token) for token in tokens]
    return stemmed_tokens


stop_words = stopwords.words('english')


def cria_tfidf_vector():
    tfidf_vectorizer = TfidfVectorizer(tokenizer=stem_tokenizar, stop_words=stop_words)
    return tfidf_vectorizer
