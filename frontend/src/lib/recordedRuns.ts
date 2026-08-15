/**
 * Four runs this system actually performed, lifted from `data/showcase.json`.
 *
 * The routing verdicts, agent lists, sources, reasoning steps and timings are
 * what the deployed pipeline produced. Answers and step names are truncated to
 * fit the monitor, and the answers' bullet lists are flattened into sentences;
 * nothing is otherwise reworded. The landing page replays these, so the panel a
 * visitor sees first is a record rather than a mock-up.
 *
 * Ordered by how much machinery the router decided each question was worth, which
 * is the point the page is making. The replay opens on the second so a visitor's
 * first sight is an answered question, and wraps from the most expensive run
 * straight back to the refused one.
 */

export type Tone = 'plain' | 'signal' | 'flag'

export interface RunLine {
  label: string
  value: string
  tone?: Tone
}

export interface RecordedRun {
  id: string
  /** What the router spent on this question, in plain words. */
  cost: string
  query: string
  lines: RunLine[]
  reasoning?: { steps: number; shown: string[] }
  answer: string
  mode: string
  latencyMs: number
}

export const RECORDED_RUNS: RecordedRun[] = [
  {
    id: 'non-medical',
    cost: 'no agents',
    query: 'Write me a poem about the sea.',
    lines: [
      { label: 'medical', value: 'no', tone: 'flag' },
      { label: 'decision', value: 'refused at the router' },
      { label: 'agents', value: 'none activated' },
      { label: 'sources', value: 'none queried' },
      { label: 'spent', value: 'one routing call' },
    ],
    answer:
      'This request falls outside the scope of medical information. I am designed to assist with medical queries.',
    mode: 'rejected',
    latencyMs: 8032,
  },
  {
    id: 'warfarin-basics',
    cost: 'one agent',
    query: 'What is Warfarin used for?',
    lines: [
      { label: 'medical', value: 'yes', tone: 'signal' },
      { label: 'intent', value: 'drug_info' },
      { label: 'complexity', value: '2 / 5' },
      { label: 'agents', value: 'researcher' },
      { label: 'sources', value: 'graph_db · web_search' },
    ],
    answer:
      'Warfarin is a blood thinner (anticoagulant) that is prescribed to prevent or treat blood clots that can be harmful…',
    mode: 'sequential',
    latencyMs: 36557,
  },
  {
    id: 'aspirin-warfarin',
    cost: 'two agents, in parallel',
    query: 'Can I take Aspirin with Warfarin?',
    lines: [
      { label: 'medical', value: 'yes', tone: 'signal' },
      { label: 'intent', value: 'interaction' },
      { label: 'complexity', value: '3 / 5' },
      { label: 'agents', value: 'researcher · validator' },
      { label: 'sources', value: 'graph_db' },
      { label: 'confidence', value: '0.90' },
    ],
    reasoning: {
      steps: 5,
      shown: [
        'Identify the two drugs involved',
        'Determine the primary intent',
        'Query medical knowledge bases (graph_db/cypher) for known interactions…',
      ],
    },
    answer:
      'Taking Aspirin with Warfarin is generally not recommended due to a significant drug interaction. This combination leads to a substantially increased risk of bleeding, which can be severe.',
    mode: 'parallel',
    latencyMs: 24542,
  },
  {
    id: 'aspirin-contraindications',
    cost: 'two agents and generated Cypher',
    query: 'Find all contraindications for Aspirin.',
    lines: [
      { label: 'medical', value: 'yes', tone: 'signal' },
      { label: 'intent', value: 'contraindication' },
      { label: 'complexity', value: '3 / 5' },
      { label: 'agents', value: 'researcher · validator' },
      { label: 'sources', value: 'graph_db · cypher · web_search' },
    ],
    reasoning: {
      steps: 4,
      shown: [
        'Identify target drug and information required',
        'Utilize graph_db and cypher to query the knowledge graph',
        'The validator agent will review and consolidate the information',
      ],
    },
    answer:
      'The contraindications for Aspirin are: stomach ulcers, which Aspirin can exacerbate; bleeding disorders, because Aspirin inhibits platelet aggregation; NSAID-precipitated bronchospasm…',
    mode: 'sequential',
    latencyMs: 53196,
  },
]

/** Opens on an answered question rather than on the refusal. */
export const OPENING_RUN = 1
