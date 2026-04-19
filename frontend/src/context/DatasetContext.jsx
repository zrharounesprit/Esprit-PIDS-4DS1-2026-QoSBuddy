import { createContext, useContext, useState } from 'react'

const DatasetContext = createContext(null)

export function DatasetProvider({ children }) {
  const [dataset, setDataset] = useState(null)
  // dataset shape: { name: string, rows: number, columns: string[], data: object[] }

  const clearDataset = () => setDataset(null)

  return (
    <DatasetContext.Provider value={{ dataset, setDataset, clearDataset }}>
      {children}
    </DatasetContext.Provider>
  )
}

export function useDataset() {
  const ctx = useContext(DatasetContext)
  if (!ctx) throw new Error('useDataset must be used inside DatasetProvider')
  return ctx
}
