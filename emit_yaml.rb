require 'cast-to-yaml'
require 'yaml'

$parser = C::Parser::new
ast = $parser.parse(File.read(ARGV[0]))


puts YAML::dump(ast.to_h)