#
# Pyserini: Reproducible IR research with sparse and dense representations
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Integration tests for TASB model using on-the-fly query encoding."""

import os
import socket
import unittest

from integrations.utils import clean_files, run_command, parse_score
from pyserini.search import QueryEncoder
from pyserini.search import get_topics


class TestSearchIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_files = []
        self.threads = 16
        self.batch_size = 256

        # Hard-code larger values for internal servers
        if socket.gethostname().startswith('damiano') or socket.gethostname().startswith('orca'):
            self.threads = 36
            self.batch_size = 144

    def test_msmarco_passage_distilbert_tas_b_bf_otf(self):
        output_file = 'test_run.msmarco-passage.distilbert-dot-tas_b-b256.bf.tsv'
        self.temp_files.append(output_file)
        cmd1 = f'python -m pyserini.search.faiss --topics msmarco-passage-dev-subset \
                             --index msmarco-passage-distilbert-dot-tas_b-b256-bf \
                             --encoder sebastian-hofstaetter/distilbert-dot-tas_b-b256-msmarco \
                             --batch-size {self.batch_size} \
                             --threads {self.threads} \
                             --output {output_file} \
                             --output-format msmarco'
        cmd2 = f'python -m pyserini.eval.msmarco_passage_eval msmarco-passage-dev-subset {output_file}'
        status = os.system(cmd1)
        stdout, stderr = run_command(cmd2)
        score = parse_score(stdout, "MRR @10")
        self.assertEqual(status, 0)
        self.assertAlmostEqual(score, 0.3443, delta=0.0001)

    def test_msmarco_passage_distilbert_kd_tas_b_encoded_queries(self):
        encoder = QueryEncoder.load_encoded_queries('distilbert_tas_b-msmarco-passage-dev-subset')
        topics = get_topics('msmarco-passage-dev-subset')
        for t in topics:
            self.assertTrue(topics[t]['title'] in encoder.embedding)

    def tearDown(self):
        clean_files(self.temp_files)


if __name__ == '__main__':
    unittest.main()
