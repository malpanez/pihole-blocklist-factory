@Library('paas') _

// Multibranch: paasPipeline reads pipeline.yml and does `checkout scm`
// (the branch/PR Jenkins is building). No `repository:` needed here.
paasPipeline(readYaml(file: 'pipeline.yml'))
