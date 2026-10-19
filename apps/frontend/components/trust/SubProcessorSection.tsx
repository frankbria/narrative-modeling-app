import { SUB_PROCESSORS } from '@/lib/legal/company'

/** The same list, from the same source, as the Privacy Policy's section 4. */
export function SubProcessorSection() {
  const processors = SUB_PROCESSORS
  return (
    <section aria-labelledby="sub-processors-heading" id="sub-processors">
      <h2 id="sub-processors-heading">Sub-processors</h2>
      <p>These third parties process data on our behalf, and what each one does with it.</p>
      <table>
        <thead>
          <tr>
            <th scope="col">Sub-processor</th>
            <th scope="col">What it does with your data</th>
          </tr>
        </thead>
        <tbody>
          {processors.map((processor) => (
            <tr key={processor.name}>
              <td className="whitespace-nowrap">
                <a href={processor.privacyUrl} target="_blank" rel="noopener noreferrer">
                  {processor.name}
                </a>
              </td>
              <td>{processor.purpose}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
