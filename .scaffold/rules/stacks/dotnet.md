# .NET Stack Rules

## Build & Test

- Primary commands: `dotnet build`, `dotnet test`, `dotnet run`
- Always run `dotnet build` before `dotnet test` to catch compilation errors early
- Use `dotnet test --verbosity normal` for meaningful output

## Conventions

- Follow existing namespace and project structure
- Prefer `async/await` patterns for I/O operations
- Use dependency injection as established in the project

## Safe Commands

dotnet build, dotnet test, dotnet run, dotnet restore, dotnet clean, dotnet format
