import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import sys
def main():
    # Handle command line args
    args: int = len(sys.argv)
    if args != 2:
        print("INCORRECT NUMBER OF ARGS\n")
        print("Usage: python3 parser.py <header file path>")
        sys.exit(-1)

    header_path: str = str(sys.argv[1])

    # Read in file to string
    file = open(header_path)
    input: str = file.read()

    # Load language
    C_LANGUAGE = Language(tsc.language())

    # Create parser
    parser = Parser(C_LANGUAGE)

    # Parse header file and store tree
    tree = parser.parse(bytes(input, "utf-8"))

    print(tree.root_node.sexp())

if __name__ == "__main__":
    main()
