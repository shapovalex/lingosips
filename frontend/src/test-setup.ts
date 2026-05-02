import "@testing-library/jest-dom"

// Provide a proper localStorage mock for Vitest's jsdom environment.
// Zustand's persist middleware calls window.localStorage.setItem which needs
// to be a real function, not just a property descriptor from jsdom's stub.
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
})()

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true,
})
