/**
 * JSON imports (Vite bundles them) as `unknown`: the mock fixtures are the backend's responses and are typed
 * where they are read (src/mocks/ev.ts), so the type checker need not infer a type for half a megabyte of
 * literal JSON (what `resolveJsonModule` would make it do).
 */
declare module "*.json" {
  const value: unknown
  export default value
}
