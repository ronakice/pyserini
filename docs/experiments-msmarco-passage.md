# Pyserini: BM25 Baseline for MS MARCO Passage Retrieval

This guide contains instructions for running BM25 baselines on the [MS MARCO *passage* ranking task](https://microsoft.github.io/msmarco/), which is nearly identical to a [similar guide in Anserini](https://github.com/castorini/anserini/blob/master/docs/experiments-msmarco-passage.md), except that everything is in Python here (no Java).
Note that there is a separate guide for the [MS MARCO *document* ranking task](experiments-msmarco-doc.md).

**Setup Note:** If you're instantiating an Ubuntu VM on your system or on cloud (AWS and GCP), try to provision enough resources such as RAM > 6GB and storage ~ 100 (can also be around 70 - 80 for this task) GB (SSD). This will prevent going back and fixing machine configuration again and again. If you get a configuration which works for Anserini on this task, it will work with Pyserini as well.

## Data Prep

The guide requires the [development installation](https://github.com/castorini/pyserini/blob/master/docs/installation.md#development-installation) for additional resource that are not shipped with the Python module.

We're going to use `collections/msmarco-passage/` as the working directory.
First, we need to download and extract the MS MARCO passage dataset:

```bash
mkdir collections/msmarco-passage

wget https://msmarco.blob.core.windows.net/msmarcoranking/collectionandqueries.tar.gz -P collections/msmarco-passage

# Alternative mirror:
# wget https://www.dropbox.com/s/9f54jg2f71ray3b/collectionandqueries.tar.gz -P collections/msmarco-passage

tar xvfz collections/msmarco-passage/collectionandqueries.tar.gz -C collections/msmarco-passage
```

To confirm, `collectionandqueries.tar.gz` should have MD5 checksum of `31644046b18952c1386cd4564ba2ae69`.

Next, we need to convert the MS MARCO tsv collection into Anserini's jsonl files (which have one json object per line):

```bash
python tools/scripts/msmarco/convert_collection_to_jsonl.py \
 --collection-path collections/msmarco-passage/collection.tsv \
 --output-folder collections/msmarco-passage/collection_jsonl
```

The above script should generate 9 jsonl files in `collections/msmarco-passage/collection_jsonl`, each with 1M lines (except for the last one, which should have 841,823 lines).

We can now index these docs as a `JsonCollection` using Anserini:

```bash
python -m pyserini.index.lucene \
  --collection JsonCollection \
  --input collections/msmarco-passage/collection_jsonl \
  --index indexes/lucene-index-msmarco-passage \
  --generator DefaultLuceneDocumentGenerator \
  --threads 9 \
  --storePositions --storeDocvectors --storeRaw
```


Upon completion, we should have an index with 8,841,823 documents.
The indexing speed may vary; on a modern desktop with an SSD, indexing takes a couple of minutes.

## Performing Retrieval on the Dev Queries

The 6980 queries in the development set are already stored in the repo.
Let's take a peek:

```bash
$ head tools/topics-and-qrels/topics.msmarco-passage.dev-subset.txt
1048585	what is paula deen's brother
2	 Androgen receptor define
524332	treating tension headaches without medication
1048642	what is paranoid sc
524447	treatment of varicose veins in legs
786674	what is prime rate in canada
1048876	who plays young dr mallard on ncis
1048917	what is operating system misconfiguration
786786	what is priority pass
524699	tricare service number

$ wc tools/topics-and-qrels/topics.msmarco-passage.dev-subset.txt
    6980   48335  290193 tools/topics-and-qrels/topics.msmarco-passage.dev-subset.txt
```

Each line contains a tab-delimited (query id, query) pair.
Conveniently, Pyserini already knows how to load and iterate through these pairs.
We can now perform retrieval using these queries:

```bash
python -m pyserini.search.lucene \
  --index indexes/lucene-index-msmarco-passage \
  --topics msmarco-passage-dev-subset \
  --output runs/run.msmarco-passage.bm25tuned.txt \
  --output-format msmarco \
  --hits 1000 \
  --bm25 --k1 0.82 --b 0.68
```

Here, we set the BM25 parameters to `k1=0.82`, `b=0.68` (tuned by grid search).
The option `--output-format msmarco` says to generate output in the MS MARCO output format.
The option `--hits` specifies the number of documents to return per query.
Thus, the output file should have approximately 6980 × 1000 = 6.9M lines.

Retrieval speed will vary by hardware:
On a reasonably modern CPU with an SSD, we might get around 13 qps (queries per second), and so the entire run should finish in under ten minutes (using a single thread).
We can perform multi-threaded retrieval by using the `--threads` and `--batch-size` arguments.
For example, setting `--threads 16 --batch-size 64` on a CPU with sufficient cores, the entire run will finish in a couple of minutes.

After the run finishes, we can evaluate the results using the official MS MARCO evaluation script:

```bash
$ python tools/scripts/msmarco/msmarco_passage_eval.py \
   tools/topics-and-qrels/qrels.msmarco-passage.dev-subset.txt runs/run.msmarco-passage.bm25tuned.txt

#####################
MRR @10: 0.18741227770955546
QueriesRanked: 6980
#####################
```

We can also use the official TREC evaluation tool, `trec_eval`, to compute metrics other than MRR@10.
For that we first need to convert the run file into TREC format:

```bash
python -m pyserini.eval.convert_msmarco_run_to_trec_run \
   --input runs/run.msmarco-passage.bm25tuned.txt \
   --output runs/run.msmarco-passage.bm25tuned.trec

python tools/scripts/msmarco/convert_msmarco_to_trec_qrels.py \
   --input tools/topics-and-qrels/qrels.msmarco-passage.dev-subset.txt \
   --output collections/msmarco-passage/qrels.dev.small.trec
```

And then run the `trec_eval` tool:

```bash
$ tools/eval/trec_eval.9.0.4/trec_eval -c -mrecall.1000 -mmap \
   collections/msmarco-passage/qrels.dev.small.trec runs/run.msmarco-passage.bm25tuned.trec

map                   	all	0.1957
recall_1000           	all	0.8573
```

Average precision or AP (also called mean average precision, MAP) and recall@1000 (recall at rank 1000) are the two metrics we care about the most.
AP captures aspects of both precision and recall in a single metric, and is the most common metric used by information retrieval researchers.
On the other hand, recall@1000 provides the upper bound effectiveness of downstream reranking modules (i.e., rerankers are useless if there isn't a relevant document in the results).

## Reproduction Log[*](reproducibility.md)

+ Results reproduced by [@JeffreyCA](https://github.com/JeffreyCA) on 2020-09-14 (commit [`49fd7cb`](https://github.com/castorini/pyserini/commit/49fd7cb8fd802493dc34f5cb33767d2e72e19f13))
+ Results reproduced by [@jhuang265](https://github.com/jhuang265) on 2020-09-14 (commit [`2ed2acc`](https://github.com/castorini/pyserini/commit/2ed2acc62e445e3e887c6cf853ccc0b0b3b57534))
+ Results reproduced by [@Dahlia-Chehata](https://github.com/Dahlia-Chehata) on 2020-11-11 (commit [`8172015`](https://github.com/Dahlia-Chehata/pyserini/commit/817201553d790c8b53a3aef17ed87721a9d35595))
+ Results reproduced by [@rakeeb123](https://github.com/rakeeb123) on 2020-12-07 (commit [`3bcd4e5`](https://github.com/castorini/pyserini/commit/3bcd4e52beb327d55ae6d3c8f6bc94351a6d1449))
+ Results reproduced by [@jrzhang12](https://github.com/jrzhang12) on 2021-01-03 (commit [`7caedfc`](https://github.com/castorini/pyserini/commit/7caedfc150f916de302297406c45dead27b475ba))
+ Results reproduced by [@HEC2018](https://github.com/HEC2018) on 2021-01-04 (commit [`46a6d47`](https://github.com/castorini/pyserini/commit/46a6d472267a559152495d004c2a12f8e95e53f0))
+ Results reproduced by [@KaiSun314](https://github.com/KaiSun314) on 2021-01-08 (commit [`aeec31f`](https://github.com/castorini/pyserini/commit/aeec31fbe17d39ecf3081597b4832f5af57ea549))
+ Results reproduced by [@yemiliey](https://github.com/yemiliey) on 2021-01-18 (commit [`98f3236`](https://github.com/castorini/pyserini/commit/98f323659c8a0a5d8ef26bb3f6768458a34e3eb9))
+ Results reproduced by [@larryli1999](https://github.com/larryli1999) on 2021-01-22 (commit [`74a87e4`](https://github.com/castorini/pyserini/commit/74a87e4951c98d7b066273140576d3cccd9ea0ed))
+ Results reproduced by [@ArthurChen189](https://github.com/ArthurChen189) on 2021-04-08 (commit [`7261223`](https://github.com/castorini/pyserini/commit/72612232bc886e71e8de9431a899a7c68f1d82c7))
+ Results reproduced by [@printfCalvin](https://github.com/printfCalvin) on 2021-04-12 (commit [`0801f7f`](https://github.com/castorini/pyserini/commit/0801f7fb15e249f2e67901a6523d6ce68c667207))
+ Results reproduced by [@saileshnankani](https://github.com/saileshnankani) on 2021-04-26 (commit [`6d48609`](https://github.com/castorini/pyserini/commit/6d486094137a26c8a0a57652a06ab4d42d5bce32))
+ Results reproduced by [@andrewyguo](https://github.com/andrewyguo) on 2021-04-30 (commit [`ecfed61`](https://github.com/castorini/pyserini/commit/ecfed61bfba065aa958848cff96ba9f22609aeb1))
+ Results reproduced by [@mayankanand007](https://github.com/mayankanand007) on 2021-05-04 (commit [`a9d6f66`](https://github.com/castorini/pyserini/commit/a9d6f66234b5dd2859a0dc116ef3e38a52d0f81d)) 
+ Results reproduced by [@rootofallevii](https://github.com/rootofallevii) on 2021-05-14 (commit [`e764797`](https://github.com/castorini/pyserini/commit/e764797081eebf487fa7e1fa34872a59ff97fdf7))
+ Results reproduced by [@jpark621](https://github.com/jpark621) on 2021-06-13 (commit [`f614111`](https://github.com/castorini/pyserini/commit/f614111f014b7490f75e585e610f64f769164dd2))
+ Results reproduced by [@nimasadri11](https://github.com/nimasadri11) on 2021-06-28 (commit [`d31e2e6`](https://github.com/castorini/pyserini/commit/d31e2e67984f3a8285589fb162080ac9570fcbe7))
+ Results reproduced by [@mzzchy](https://github.com/mzzchy) on 2021-07-05 (commit [`45083f5`](https://github.com/castorini/pyserini/commit/45083f5ecb986651301c1fe26d09981d0baee8ee))
+ Results reproduced by [@d1shs0ap](https://github.com/d1shs0ap) on 2021-07-16 (commit [`a6b6545`](https://github.com/castorini/pyserini/commit/a6b6545c0133c03d50d5c33fb2fea7c527de04bb))
+ Results reproduced by [@apokali](https://github.com/apokali) on 2021-08-19 (commit[`45a2fb4`](https://github.com/castorini/pyserini/commit/45a2fb4bacbbd92f54ff0f98463662cbc09d78bb))
+ Results reproduced by [@leungjch](https://github.com/leungjch) on 2021-09-12 (commit [`c71a69e`](https://github.com/castorini/pyserini/commit/c71a69e2dfad487e492b9b2b3c21b9b9c2e7cdb5))
+ Results reproduced by [@AlexWang000](https://github.com/AlexWang000) on 2021-10-10 (commit [`8599c81`](https://github.com/castorini/pyserini/commit/8599c81a0f0b1c09c32669c26c7e62dec6e4020d))
+ Results reproduced by [@manveertamber](https://github.com/manveertamber) on 2021-12-05 (commit [`c280dad`](https://github.com/castorini/pyserini/commit/c280dad1618c1f985f84fe35bb66aaadcf98131b))
+ Results reproduced by [@lingwei-gu](https://github.com/lingwei-gu) on 2021-12-15 (commit [`7249409`](https://github.com/castorini/pyserini/commit/7249409269095cd65259eb8a7c5131d3b9323068))
+ Results reproduced by [@tyao-t](https://github.com/tyao-t) on 2021-12-19 (commit [`fc54ed6`](https://github.com/castorini/pyserini/commit/fc54de6725ef1c973831f5c239facb8f03f32ad5))
+ Results reproduced by [@kevin-wangg](https://github.com/kevin-wangg) on 2022-01-05 (commit [`b9fcae7`](https://github.com/castorini/pyserini/commit/b9fcae7994fad0d1943f0f8054d84982c23a9954))
+ Results reproduced by [@vivianliu0](https://github.com/vivianliu0) on 2021-01-06 (commit [`937ec63`](https://github.com/castorini/pyserini/commit/937ec63deead4d6743a735d78d381792067469e7))
+ Results reproduced by [@mikhail-tsir](https://github.com/mikhail-tsir) on 2022-01-10 (commit [`f1084a0`](https://github.com/castorini/pyserini/commit/f1084a05a3bf955bdd27acd33f2b95c636b2e5b6))
+ Results reproduced by [@AceZhan](https://github.com/AceZhan) on 2022-01-14 (commit [`68be809`](https://github.com/castorini/pyserini/commit/68be8090b8553fc6eaf352ac690a6de9d3dc82dd))
+ Results reproduced by [@jh8liang](https://github.com/jh8liang) on 2022-02-06 (commit [`e03e068`](https://github.com/castorini/pyserini/commit/e03e06880ad4f6d67a1666c1dd45ce4250adc95d))
+ Results reproduced by [@HAKSOAT](https://github.com/HAKSOAT) on 2022-03-10 (commit [`7796685`](https://github.com/castorini/pyserini/commit/77966851755163e36489544fb08f73171e98103f))
+ Results reproduced by [@jasper-xian](https://github.com/jasper-xian) on 2022-03-27 (commit [`5668edd`](https://github.com/castorini/pyserini/commit/5668edd6f1e61e9c57d600d41d3d1f58b775d371))
+ Results reproduced by [@jx3yang](https://github.com/jx3yang) on 2022-04-25 (commit [`53333e0`](https://github.com/castorini/pyserini/commit/53333e0fb77371e049e24b10da3a20646c7b5af7))
+ Results reproduced by [@alvind1](https://github.com/alvind1) on 2022-05-04 (commit [`244828f`](https://github.com/castorini/pyserini/commit/244828f6d6d70a7405e0906a700a5ce8ef0def15))
+ Results reproduced by [@Pie31415](https://github.com/Pie31415) on 2022-06-20 (commit [`52db3a7`](https://github.com/castorini/pyserini/commit/52db3a7e8087ae351b69d00c9a3fe3450db4b328))
+ Results reproduced by [@aivan6842](https://github.com/aivan6842) on 2022-07-11 (commit [`f553d43`](https://github.com/castorini/pyserini/commit/f553d43e5bd0b5617a002f1ab7861a158d6e2e71))
+ Results reproduced by [@Jasonwu-0803](https://github.com/Jasonwu-0803) on 2022-09-27 (commit [`563e4e7`](https://github.com/castorini/pyserini/commit/563e4e7d0daa2869355952663ed3f68955cdefdc))
+ Results reproduced by [@limelody](https://github.com/limelody) on 2022-09-27 (commit [`7b53918`](https://github.com/castorini/pyserini/commit/7b5391864897df4523b34a4943ce08d7e373dbe7))
