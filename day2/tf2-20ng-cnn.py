
# coding: utf-8

# # 20 Newsgroups text classification with pre-trained word embeddings
# 
# In this notebook, we'll use pre-trained [GloVe word
# embeddings](http://nlp.stanford.edu/projects/glove/) for text
# classification using TensorFlow 2.0 / Keras. This notebook is
# largely based on the blog post [Using pre-trained word embeddings in
# a Keras model]
# (https://blog.keras.io/using-pre-trained-word-embeddings-in-a-keras-model.html)
# by François Chollet.
# 
# **Note that using a GPU with this notebook is highly recommended.**
# 
# First, the needed imports.

import tensorflow as tf

from tensorflow.keras.preprocessing import sequence, text
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.layers import Embedding
from tensorflow.keras.layers import Conv1D, MaxPooling1D, GlobalMaxPooling1D, LSTM
from tensorflow.keras.utils import to_categorical

from tensorflow.keras.callbacks import TensorBoard
from tensorflow.keras.utils import plot_model

from zipfile import ZipFile
import os, datetime
import sys

import numpy as np

print('Using Tensorflow version:', tf.__version__,
      'Keras version:', tf.keras.__version__,
      'backend:', tf.keras.backend.backend(), flush=True)

# ## GloVe word embeddings
# 
# Let's begin by loading a datafile containing pre-trained word
# embeddings. The datafile contains 100-dimensional embeddings for
# 400,000 English words.

if 'DATADIR' in os.environ:
    DATADIR = os.environ['DATADIR']
else:
    DATADIR = "/scratch/project_2000745/data/"

GLOVE_DIR = os.path.join(DATADIR, "glove.6B")

print('Indexing word vectors.')

embeddings_index = {}
with open(os.path.join(GLOVE_DIR, 'glove.6B.100d.txt')) as f:
    for line in f:
        values = line.split()
        word = values[0]
        coefs = np.asarray(values[1:], dtype='float32')
        embeddings_index[word] = coefs

print('Found %s word vectors.' % len(embeddings_index))

# ## 20 Newsgroups data set
# 
# Next we'll load the [20 Newsgroups]
# (http://www.cs.cmu.edu/afs/cs.cmu.edu/project/theo-20/www/data/news20.html)
# data set.
# 
# The dataset contains 20000 messages collected from 20 different
# Usenet newsgroups (1000 messages from each group):
# 
# alt.atheism           | soc.religion.christian   | comp.windows.x     | sci.crypt               
# talk.politics.guns    | comp.sys.ibm.pc.hardware | rec.autos          | sci.electronics     
# talk.politics.mideast | comp.graphics            | rec.motorcycles    | sci.space
# talk.politics.misc    | comp.os.ms-windows.misc  | rec.sport.baseball | sci.med
# talk.religion.misc    | comp.sys.mac.hardware    | rec.sport.hockey   | misc.forsale

TEXT_DATA_ZIP = os.path.join(DATADIR, "20_newsgroup.zip")
zf = ZipFile(TEXT_DATA_ZIP, 'r')

print('Processing text dataset from', TEXT_DATA_ZIP, flush=True)

texts = []  # list of text samples
labels_index = {}  # dictionary mapping label name to numeric id
labels = []  # list of label ids
for fullname in sorted(zf.namelist()):
    parts = fullname.split('/')
    dirname = parts[1]
    fname = parts[2] if len(parts) > 2 else None
    zinfo = zf.getinfo(fullname)
    if zinfo.is_dir() and len(dirname) > 0:
        label_id = len(labels_index)
        labels_index[dirname] = label_id
        print(dirname, label_id)
    elif fname is not None and fname.isdigit():
        with zf.open(fullname) as f:
            t = f.read().decode('latin-1')
            i = t.find('\n\n')  # skip header
            if 0 < i:
                t = t[i:]
            texts.append(t)
        labels.append(label_id)

print('Found %s texts.' % len(texts))

# ### Vectorization
# 
# Vectorize the text samples into a 2D integer tensor.

MAX_NUM_WORDS = 10000
MAX_SEQUENCE_LENGTH = 1000 

tokenizer = text.Tokenizer(num_words=MAX_NUM_WORDS)
tokenizer.fit_on_texts(texts)
sequences = tokenizer.texts_to_sequences(texts)

word_index = tokenizer.word_index
print('Found %s unique tokens.' % len(word_index))

data = sequence.pad_sequences(sequences, maxlen=MAX_SEQUENCE_LENGTH)

labels = to_categorical(np.asarray(labels))
print('Shape of data tensor:', data.shape)
print('Shape of label tensor:', labels.shape)

# ### TF Datasets
# 
# Let's now define our TF Datasets
# (https://www.tensorflow.org/versions/r2.0/api_docs/python/tf/data/Dataset#class_dataset)
# for training, validation, and test data.

VALIDATION_SET, TEST_SET = 1000, 4000
BATCH_SIZE = 128 

dataset = tf.data.Dataset.from_tensor_slices((data, labels))
dataset = dataset.shuffle(20000)

train_dataset = dataset.skip(VALIDATION_SET+TEST_SET)
train_dataset = train_dataset.batch(BATCH_SIZE, drop_remainder=True)

validation_dataset = dataset.skip(TEST_SET).take(VALIDATION_SET)
validation_dataset = validation_dataset.batch(BATCH_SIZE, drop_remainder=True)

test_dataset = dataset.take(TEST_SET)
test_dataset = test_dataset.batch(BATCH_SIZE, drop_remainder=False)

# ### Pretrained embedding matrix
# 
# As the last step in data preparation, we construct the GloVe
# embedding matrix:

print('Preparing embedding matrix.')

num_words = min(MAX_NUM_WORDS, len(word_index) + 1)
embedding_dim = 100

embedding_matrix = np.zeros((num_words, embedding_dim))
for word, i in word_index.items():
    if i >= MAX_NUM_WORDS:
        continue
    embedding_vector = embeddings_index.get(word)
    if embedding_vector is not None:
        # words not found in embedding index will be all-zeros.
        embedding_matrix[i] = embedding_vector
        
print('Shape of embedding matrix:', embedding_matrix.shape)

# ## 1-D CNN
# 
# ### Initialization

print('Build model...')
model = Sequential()

model.add(Embedding(num_words,
                    embedding_dim,
                    weights=[embedding_matrix],
                    input_length=MAX_SEQUENCE_LENGTH,
                    trainable=False))

model.add(Conv1D(128, 5, activation='relu'))
model.add(MaxPooling1D(5))
model.add(Conv1D(128, 5, activation='relu'))
model.add(MaxPooling1D(5))
model.add(Conv1D(128, 5, activation='relu'))
model.add(GlobalMaxPooling1D())

model.add(Dense(128, activation='relu'))
model.add(Dense(20, activation='softmax'))

model.compile(loss='categorical_crossentropy',
              optimizer='rmsprop',
              metrics=['accuracy'])

print(model.summary())

# ### Learning

logdir = os.path.join(os.getcwd(), "logs",
                      "20ng-cnn-"+datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
print('TensorBoard log directory:', logdir)
os.makedirs(logdir)
callbacks = [TensorBoard(log_dir=logdir)]

epochs = 10

history = model.fit(train_dataset, epochs=epochs,
                    validation_data=validation_dataset,
                    verbose=2, callbacks=callbacks)

# ### Inference
# 
# We evaluate the model using the test set. If accuracy on the test
# set is notably worse than with the training set, the model has
# likely overfitted to the training samples.

test_scores = model.evaluate(test_dataset, verbose=2)
print("Test set %s: %.2f%%" % (model.metrics_names[1], test_scores[1]*100))
