module.exports = {
  ...require('prettier-config-ackama'),
  plugins: ['prettier-plugin-jinja-template'],
  overrides: [
    {
      files: ['web/templates/**'],
      options: { parser: 'jinja-template' }
    }
  ]
};
