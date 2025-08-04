# Refactoring Plan for C++ MCP Server

## Current State
- `cpp_analyzer.py`: 1142 lines - Contains all analysis logic
- `cpp_mcp_server.py`: 1631 lines - Contains MCP server implementation

## Proposed Module Structure

### 1. Core Modules

#### `symbol_info.py` (~50 lines)
- Move `SymbolInfo` dataclass
- Keep it as a shared data structure

#### `cache_manager.py` (~200 lines)
- Extract all caching logic from `cpp_analyzer.py`
- Methods: `save_cache()`, `load_cache()`, `get_cache_path()`, etc.
- Handle file hashing and cache validation

#### `file_scanner.py` (~150 lines)
- Extract file discovery logic
- Methods: `find_cpp_files()`, `should_skip_file()`, `should_skip_directory()`
- Handle include/exclude patterns

#### `symbol_parser.py` (~300 lines)
- Extract libclang parsing logic
- Methods: `parse_file()`, `process_cursor()`, `get_base_classes()`
- Handle AST traversal and symbol extraction

#### `call_graph.py` (~200 lines)
- Extract call graph functionality
- Methods: `find_callers()`, `find_callees()`, `get_call_path()`
- Manage call graph and reverse call graph data structures

#### `search_engine.py` (~150 lines)
- Extract search functionality
- Methods: `search_classes()`, `search_functions()`, `search_symbols()`
- Handle regex patterns and filtering

#### `cpp_analyzer.py` (~200 lines, reduced from 1142)
- Keep as the main coordinator class
- Import and use the other modules
- Maintain the public API

### 2. MCP Server Modules

#### `tool_definitions.py` (~300 lines)
- Extract all tool definitions
- Keep tool schemas in one place

#### `tool_handlers.py` (~400 lines)
- Extract all tool handler implementations
- One function per tool

#### `mcp_utils.py` (~100 lines)
- Extract utility functions
- Project root detection, error handling, etc.

#### `cpp_mcp_server.py` (~300 lines, reduced from 1631)
- Keep as the main MCP server entry point
- Import tool definitions and handlers
- Handle server lifecycle

## Benefits
1. **Maintainability**: Easier to find and modify specific functionality
2. **Testability**: Can unit test individual modules
3. **Reusability**: Modules can be used independently
4. **Clarity**: Clear separation of concerns
5. **Performance**: No impact on performance, just organization

## Implementation Order
1. Start with `symbol_info.py` (easiest, no dependencies)
2. Extract `cache_manager.py` (clear boundaries)
3. Extract `file_scanner.py` (independent functionality)
4. Extract `call_graph.py` (well-defined purpose)
5. Extract `search_engine.py` (clear interface)
6. Extract `symbol_parser.py` (core parsing logic)
7. Refactor MCP server modules

## Backwards Compatibility
- Keep all public APIs the same
- Existing imports (`from cpp_analyzer import CppAnalyzer`) will still work
- No changes needed to test scripts or MCP clients